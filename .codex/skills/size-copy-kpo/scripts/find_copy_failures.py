#!/usr/bin/env python3
"""List failed client copy tasks for one local calendar day (read-only)."""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class Region:
    name: str
    host: str
    username_env: str
    password_env: str


REGIONS = (
    Region("US-01", "https://airflow-us01.precisionlender.com", "USAIRFLORUSER", "USAIRFLOWPASSWORD"),
    Region("CA-02", "https://airflow-ca02.precisionlender.com", "CAAIRFLORUSER", "CAAIRFLOWPASSWORD"),
)


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key.isidentifier() and key not in os.environ:
            os.environ[key] = value.strip().strip("'\"")


def day_window(value: str) -> tuple[datetime, datetime]:
    target = date.fromisoformat(value)
    local_tz = datetime.now().astimezone().tzinfo
    start = datetime.combine(target, time.min, tzinfo=local_tz)
    return start, start + timedelta(days=1)


def fetch(region: Region, start: datetime, end: datetime) -> list[dict[str, object]]:
    username, password = os.environ.get(region.username_env), os.environ.get(region.password_env)
    if not username or not password:
        raise RuntimeError(f"missing {region.username_env} or {region.password_env}")
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    payload: dict[str, object] = {
        "state": ["failed"],
        "start_date_gte": start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "start_date_lte": end.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "page_limit": 1000,
        "page_offset": 0,
    }
    endpoint = f"{region.host}/api/v1/dags/~/dagRuns/~/taskInstances/list"
    results: list[dict[str, object]] = []
    while True:
        request = Request(endpoint, data=json.dumps(payload).encode(), headers={"Authorization": f"Basic {token}", "Content-Type": "application/json"}, method="POST")
        try:
            with urlopen(request, timeout=30) as response:
                page = json.load(response)
        except HTTPError as error:
            raise RuntimeError(f"Airflow API returned HTTP {error.code}") from error
        except URLError as error:
            raise RuntimeError(f"unable to reach Airflow API: {error.reason}") from error
        instances = page.get("task_instances", [])
        results.extend(instances)
        if len(results) >= page.get("total_entries", 0) or not instances:
            return results
        payload["page_offset"] = len(results)


def is_copy_task(instance: dict[str, object]) -> bool:
    return str(instance.get("dag_id", "")).startswith("l3-main-") and "_copy" in str(instance.get("task_id", ""))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default=(datetime.now().astimezone() - timedelta(days=1)).date().isoformat(), help="Local date, YYYY-MM-DD")
    parser.add_argument("--dag-id", help="Filter to one l3-main client DAG")
    parser.add_argument("--task-id", help="Filter to one copy task")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    args = parser.parse_args()
    start, end = day_window(args.date)
    load_dotenv(args.env_file)
    matches: list[tuple[str, dict[str, object]]] = []
    for region in REGIONS:
        try:
            for item in fetch(region, start, end):
                if not is_copy_task(item):
                    continue
                if args.dag_id and item.get("dag_id") != args.dag_id:
                    continue
                if args.task_id and item.get("task_id") != args.task_id:
                    continue
                matches.append((region.name, item))
        except RuntimeError as error:
            print(f"{region.name}: {error}", file=sys.stderr)
            return 1
    print(f"{len(matches)} failed copy task instance(s) on {start:%m/%d}")
    for region, item in matches:
        print(" | ".join((region, str(item.get("dag_id")), str(item.get("task_id")), str(item.get("dag_run_id")), str(item.get("start_date")))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
