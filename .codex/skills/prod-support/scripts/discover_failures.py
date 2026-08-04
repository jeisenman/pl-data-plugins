#!/usr/bin/env python3
"""Discover read-only production Airflow task failures for US-01 and CA-02."""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote_plus
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class Region:
    name: str
    host: str
    username_env: str
    password_env: str


REGIONS = (
    Region(
        name="US-01",
        host="https://airflow-us01.precisionlender.com",
        username_env="USAIRFLORUSER",
        password_env="USAIRFLOWPASSWORD",
    ),
    Region(
        name="CA-02",
        host="https://airflow-ca02.precisionlender.com",
        username_env="CAAIRFLORUSER",
        password_env="CAAIRFLOWPASSWORD",
    ),
)


def parse_local_time(value: str | None) -> datetime:
    if not value:
        return datetime.now().astimezone()
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.astimezone() if parsed.tzinfo else parsed.astimezone()


def prior_day_link(region: Region, reference_time: datetime) -> str:
    start = reference_time - timedelta(days=1)
    display_time = start.strftime("%m/%d/%Y %I:%M %p").replace(" 0", " ")
    encoded_start = quote_plus(display_time)
    return f"{region.host}/taskinstance/list/?_flt_3_state=failed&_flt_1_start_date={encoded_start}#"


def load_dotenv(env_file: Path) -> None:
    """Load simple KEY=VALUE entries without overriding exported credentials."""
    if not env_file.is_file():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key.isidentifier() or key in os.environ:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ[key] = value


def failed_task_instances(region: Region, start: datetime) -> list[dict[str, object]]:
    username = os.environ.get(region.username_env)
    password = os.environ.get(region.password_env)
    if not username or not password:
        raise RuntimeError(
            f"missing {region.username_env} or {region.password_env}; set them in the environment or .env"
        )

    authorization = base64.b64encode(f"{username}:{password}".encode()).decode()
    payload = {
        "state": ["failed"],
        "start_date_gte": start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "page_limit": 1000,
        "page_offset": 0,
    }
    failures: list[dict[str, object]] = []
    endpoint = f"{region.host}/api/v1/dags/~/dagRuns/~/taskInstances/list"

    while True:
        request = Request(
            endpoint,
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Basic {authorization}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=30) as response:
                result = json.load(response)
        except HTTPError as error:
            raise RuntimeError(f"Airflow API returned HTTP {error.code}") from error
        except URLError as error:
            raise RuntimeError(f"unable to reach Airflow API: {error.reason}") from error

        page = result.get("task_instances", [])
        failures.extend(page)
        if len(failures) >= result.get("total_entries", 0) or not page:
            return failures
        payload["page_offset"] += len(page)


def print_failures(region: Region, failures: list[dict[str, object]]) -> None:
    print(f"{region.name}: {len(failures)} failed task instance(s)")
    for failure in failures:
        print(
            "  - {dag_id} | {task_id} | {dag_run_id} | started {start_date}".format(
                dag_id=failure.get("dag_id", "<unknown DAG>"),
                task_id=failure.get("task_id", "<unknown task>"),
                dag_run_id=failure.get("dag_run_id", "<unknown run>"),
                start_date=failure.get("start_date", "<not started>"),
            )
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--at", help="Local ISO-8601 reference time; defaults to now.")
    parser.add_argument("--dry-run", action="store_true", help="Print the API time window without requesting Airflow.")
    parser.add_argument("--env-file", type=Path, default=Path(".env"), help="Credential file to load; defaults to .env.")
    args = parser.parse_args()

    reference_time = parse_local_time(args.at)
    print("URLs to validate")
    for region in REGIONS:
        print(prior_day_link(region, reference_time))

    start = reference_time - timedelta(days=1)
    if args.dry_run:
        print(f"Would query failed task instances from {start.isoformat()}")
        return 0

    load_dotenv(args.env_file)
    print("Failed task instances")
    exit_code = 0
    for region in REGIONS:
        try:
            print_failures(region, failed_task_instances(region, start))
        except RuntimeError as error:
            print(f"{region.name}: {error}", file=sys.stderr)
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
