#!/usr/bin/env python3
"""Prepare a read-only EventBus opportunity validation report from production logs."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

from azure_auth import ensure_azure_login


TASK_ID = "validate_event_bus_opportunities"
REGIONS = {
    "us01": {
        "host": "https://airflow-us01.precisionlender.com",
        "workspace": "6220c6e1-57a3-49c2-901c-bb5e5106f2b0",
    },
    "ca02": {
        "host": "https://airflow-ca02.precisionlender.com",
        "workspace": "2fc9684b-5d16-42f0-ab99-9dc044e4ea73",
    },
}
RESOURCE_APP_PAGES = (
    "https://bacprod.precisionlender.com/Admin/Troubleshooting/ResendOpportunitySnapshots",
    "https://us01-app.precisionlender.com/Admin/Troubleshooting/ResendOpportunitySnapshots",
    "https://us02-app.precisionlender.com/Admin/Troubleshooting/ResendOpportunitySnapshots",
)
CLIENT_ID = re.compile(r"ClientId:\s*([0-9a-f-]{36})", re.IGNORECASE)
OPPORTUNITY_ID = re.compile(r"OpportunityId:\s*([0-9a-f-]{36})", re.IGNORECASE)
RECOVERABLE = re.compile(r"Is Recoverable:\s*(True|False)", re.IGNORECASE)


def parse_payloads(text: str) -> dict[str, dict[bool, set[str]]]:
    """Extract ClientId/OpportunityId/Is Recoverable triples from task output."""
    grouped: dict[str, dict[bool, set[str]]] = defaultdict(lambda: defaultdict(set))
    client_id: str | None = None
    opportunity_id: str | None = None
    for line in text.splitlines():
        if match := CLIENT_ID.search(line):
            client_id = match.group(1).lower()
        if match := OPPORTUNITY_ID.search(line):
            opportunity_id = match.group(1).lower()
        if match := RECOVERABLE.search(line):
            if client_id and opportunity_id:
                grouped[client_id][match.group(1).lower() == "true"].add(opportunity_id)
                opportunity_id = None
    return grouped


def add_query_rows(payload: object, grouped: dict[str, dict[bool, set[str]]]) -> None:
    """Add grouped IDs from the expected az monitor log-analytics JSON response."""
    if not isinstance(payload, list):
        return
    for row in payload:
        if not isinstance(row, dict) or not row.get("ClientId"):
            continue
        client_id = str(row["ClientId"]).lower()
        for key, recoverable in (("RecoverableOpportunityIds", True), ("NonRecoverableOpportunityIds", False)):
            values = row.get(key) or []
            if isinstance(values, str):
                values = [values]
            for value in values:
                if OPPORTUNITY_ID.fullmatch(f"OpportunityId: {value}"):
                    grouped[client_id][recoverable].add(str(value).lower())


def kusto_query(run_id: str) -> str:
    escaped_run_id = run_id.replace("'", "''")
    return f"""DI_Scheduling_CL
| where logger_s == 'datamart.jobs.OpportunityValidation'
| where task_id_s == '{TASK_ID}'
| where run_id_s == '{escaped_run_id}'
| extend OpportunityId = extract('OpportunityId: ([0-9a-f-]+)', 1, Message),
         IsRecoverable = extract('Is Recoverable: (True|False)', 1, Message)
| where isnotempty(OpportunityId)
| summarize RecoverableOpportunityIds=make_set_if(OpportunityId, IsRecoverable == 'True'),
            NonRecoverableOpportunityIds=make_set_if(OpportunityId, IsRecoverable == 'False')
  by ClientId=client_id_g
| order by ClientId asc"""


def query_logs(region: str, run_id: str, start_utc: str, end_utc: str) -> object:
    if not ensure_azure_login():
        raise RuntimeError("Azure data-engineering login is unavailable.")
    command = [
        "az", "monitor", "log-analytics", "query", "-w", REGIONS[region]["workspace"],
        "--timespan", f"{start_utc}/{end_utc}", "--analytics-query", kusto_query(run_id), "-o", "json",
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Log Analytics query failed.")
    return json.loads(result.stdout)


def dag_link(region: str, client_id: str, run_id: str | None, execution_date: str | None) -> str:
    query = [f"task_id={TASK_ID}"]
    if run_id:
        query.append(f"dag_run_id={quote(run_id, safe='')}")
    if execution_date:
        query.append(f"execution_date={quote(execution_date, safe='')}")
    return f"{REGIONS[region]['host']}/dags/l3-main-{client_id}/grid?{'&'.join(query)}"


def print_report(grouped: dict[str, dict[bool, set[str]]], region: str, run_id: str | None, execution_date: str | None) -> None:
    if not grouped:
        print("No EventBus opportunity payloads found.")
        return
    print("DAG IDs")
    for client_id in sorted(grouped):
        print(f"l3-main-{client_id}")
        print(dag_link(region, client_id, run_id, execution_date))

    print("\nResend Opportunity Snapshots")
    print("Opportunities: Note: If more than one ID, separate by commas. The OpportunityId box accepts up to 1000 IDs; IDs after 1000 are ignored.")
    recoverable_clients: list[str] = []
    for client_id in sorted(grouped):
        ids = sorted(grouped[client_id][True])
        if not ids:
            continue
        recoverable_clients.append(client_id)
        print(f"\nClient: {client_id}")
        print(",".join(ids[:1000]))
        if len(ids) > 1000:
            print(f"WARNING: {len(ids) - 1000} recoverable IDs remain; submit them in another batch.")

    print("\nNon-recoverable / inspect separately")
    for client_id in sorted(grouped):
        ids = sorted(grouped[client_id][False])
        if ids:
            print(f"Unrecoverable opportunities for {client_id}: {len(ids)}")
            print(",".join(ids))

    print("\nResource application lookup")
    print("TODO: Obtain the approved resource-application API route and token flow before automating this lookup. No application request was made.")
    for page in RESOURCE_APP_PAGES:
        print(page)

    print("\nProd support message")
    if recoverable_clients:
        print("After operator confirmation: Events re-sent for client(s) " + ", ".join(recoverable_clients) + ".")
    else:
        print("No recoverable opportunity IDs found; no resend was attempted.")
    for client_id in sorted(grouped):
        count = len(grouped[client_id][False])
        if count:
            print(f"Unrecoverable opportunities for {client_id}: {count}")


def read_log_file(path: str) -> str:
    return sys.stdin.read() if path == "-" else Path(path).read_text()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", required=True, choices=REGIONS)
    parser.add_argument("--run-id", help="Failed Airflow DAG run ID; required when querying Log Analytics.")
    parser.add_argument("--execution-date", help="Optional Airflow execution date for the DAG link.")
    parser.add_argument("--start-utc", help="Start of the Log Analytics query window in UTC.")
    parser.add_argument("--end-utc", help="End of the Log Analytics query window in UTC.")
    parser.add_argument("--log-file", help="Parse captured task logs instead of querying Log Analytics; use - for stdin.")
    args = parser.parse_args()

    grouped: dict[str, dict[bool, set[str]]] = defaultdict(lambda: defaultdict(set))
    if args.log_file:
        grouped.update(parse_payloads(read_log_file(args.log_file)))
    else:
        if not args.run_id:
            parser.error("--run-id is required unless --log-file is provided")
        end = args.end_utc or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        start = args.start_utc or (datetime.now(timezone.utc) - timedelta(hours=24)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        try:
            add_query_rows(query_logs(args.region, args.run_id, start, end), grouped)
        except (RuntimeError, json.JSONDecodeError) as error:
            print(f"Unable to query EventBus logs: {error}", file=sys.stderr)
            return 1
    print_report(grouped, args.region, args.run_id, args.execution_date)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
