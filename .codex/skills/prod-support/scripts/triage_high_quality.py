#!/usr/bin/env python3
"""Identify safe rerun targets for Derived RA high_quality distinctness failures."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from azure_auth import ensure_azure_login


WORKSPACES = {
    "us01": "6220c6e1-57a3-49c2-901c-bb5e5106f2b0",
    "ca02": "2fc9684b-5d16-42f0-ab99-9dc044e4ea73",
}
KNOWN_JOBS = {
    "coreaccountdetails": "get_core_account_details",
    "coreaccountfinancialstatements": "get_core_account_financial_statements",
    "coredepositaccounts": "get_core_deposit_accounts",
    "depositproducts": "get_core_deposit_accounts",
    "depositfinancialstatementsbreakdown": "get_core_deposit_accounts",
    "coreloanaccounts": "get_core_loan_accounts",
    "commercialloanaccounts": "get_core_loan_accounts",
    "commercialloanproducts": "get_core_loan_accounts",
    "consumerloanaccounts": "get_core_loan_accounts",
    "consumerloanproducts": "get_core_loan_accounts",
    "coreaccountsupplementaldata": "get_core_loan_accounts",
    "coreaccountsupplimentaldata": "get_core_loan_accounts",
    "mastercommitmentloanaccounts": "get_core_loan_accounts",
    "mastercommitmentloanproducts": "get_core_loan_accounts",
    "loanfinancialstatementsbreakdown": "get_core_loan_accounts",
    "coreotheraccounts": "get_core_other_accounts",
    "otherproducts": "get_core_other_accounts",
    "otherfinancialstatementsbreakdown": "get_core_other_accounts",
    "coretreasuryaccounts": "get_core_treasury_accounts",
    "treasuryaccounts": "get_core_treasury_accounts",
    "treasuryproducts": "get_core_treasury_accounts",
    "treasurycategories": "get_core_treasury_accounts",
    "treasuryfinancialstatementbreakdown": "get_core_treasury_accounts",
    "rarelationships": "get_relationships",
    "relationships": "get_relationships",
    "relationshipfinancialstatements": "get_relationships",
    "relationshipaggregatedbalances": "get_relationships",
}
BEGIN = re.compile(r"Validate distinctness - begin:\s*(.+?)\s*$", re.IGNORECASE)
FAILURE = re.compile(r"Distinctness validation failed for\s+(.+?)\s+on\s+", re.IGNORECASE)
COUNTS = re.compile(
    r"Validate distinctness - counts:\s*(.+?)\s*-\s*total:\s*(\d+)\s*;\s*unique:\s*(\d+)",
    re.IGNORECASE,
)
TIMEOUT = re.compile(r"\*\*TimeoutError:", re.IGNORECASE)


def normalise_dataset_form(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9]", "", value)
    return re.sub(r"(?:derived|data)$", "", value, flags=re.IGNORECASE).lower()


def get_job_name(dataset_form: str) -> str:
    """Map a logged DatasetForm to the high_quality task-group factory name."""
    normalised = normalise_dataset_form(dataset_form)
    if job := KNOWN_JOBS.get(normalised):
        return job
    snake_case = re.sub(r"(?<!^)(?=[A-Z])", "_", dataset_form).lower()
    snake_case = re.sub(r"[^a-z0-9]+", "_", snake_case).strip("_")
    snake_case = re.sub(r"_(derived|data)$", "", snake_case)
    return f"get_{snake_case}"


def parse_distinctness_failures(text: str) -> set[str]:
    """Return DatasetForms whose distinctness counts do not match."""
    failures: set[str] = set()
    for line in text.splitlines():
        if match := FAILURE.search(line):
            failures.add(match.group(1).strip())
            continue
        if match := COUNTS.search(line):
            dataset, total, unique = match.groups()
            if total != unique:
                failures.add(dataset.strip())
    return failures


def kusto_query(task_id: str, run_id: str) -> str:
    task_id = task_id.replace("'", "''")
    run_id = run_id.replace("'", "''")
    return f"""DI_Scheduling_CL
| where task_id_s == '{task_id}'
| where run_id_s == '{run_id}'
| where Message has 'Validate distinctness' or Message has 'Distinctness validation failed'
| project TimeGenerated, Message
| order by TimeGenerated asc"""


def collect_message_text(payload: object) -> str:
    messages: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key.lower() in {"message", "message_s"} and isinstance(value, str):
                messages.append(value)
            else:
                messages.extend(collect_message_text(value).splitlines())
    elif isinstance(payload, list):
        for value in payload:
            messages.extend(collect_message_text(value).splitlines())
    return "\n".join(messages)


def query_logs(region: str, task_id: str, run_id: str, start_utc: str, end_utc: str) -> str:
    if not ensure_azure_login():
        raise RuntimeError("Azure data-engineering login is unavailable.")
    command = [
        "az", "monitor", "log-analytics", "query", "-w", WORKSPACES[region],
        "--timespan", f"{start_utc}/{end_utc}", "--analytics-query", kusto_query(task_id, run_id), "-o", "json",
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Log Analytics query failed.")
    return collect_message_text(json.loads(result.stdout))


def read_log_file(path: str) -> str:
    return sys.stdin.read() if path == "-" else Path(path).read_text()


def valid_high_quality_task(task_id: str) -> bool:
    return task_id.rsplit(".", 1)[-1].startswith("high_quality_")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", required=True, choices=WORKSPACES)
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--task-id", required=True, help="Failed Airflow high_quality task ID.")
    parser.add_argument("--run-id", help="Failed Airflow DAG run ID; required without --log-file.")
    parser.add_argument("--start-utc", help="Start of the Log Analytics query window in UTC.")
    parser.add_argument("--end-utc", help="End of the Log Analytics query window in UTC.")
    parser.add_argument("--log-file", help="Parse captured task logs instead; use - for stdin.")
    args = parser.parse_args()

    if not valid_high_quality_task(args.task_id):
        parser.error("--task-id must name a high_quality_* Derived RA task")
    if args.log_file:
        log_text = read_log_file(args.log_file)
    else:
        if not args.run_id:
            parser.error("--run-id is required unless --log-file is provided")
        end = args.end_utc or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        start = args.start_utc or (datetime.now(timezone.utc) - timedelta(hours=24)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        try:
            log_text = query_logs(args.region, args.task_id, args.run_id, start, end)
        except (RuntimeError, json.JSONDecodeError) as error:
            print(f"Unable to get high_quality task logs: {error}", file=sys.stderr)
            return 1

    datasets = sorted(parse_distinctness_failures(log_text))
    if not datasets:
        if TIMEOUT.search(log_text):
            print("TimeoutError detected; classify this failure as a timeout. Do not rerun from this analysis.")
            return 0
        print("No Validate distinctness errors found; do not rerun from this analysis.")
        return 0
    jobs = sorted({get_job_name(dataset) for dataset in datasets})
    print(f"Validate distinctness error on {args.client_id}; re-running:")
    print(f"l3-main-{args.client_id}")
    for job in jobs:
        print(job)
    print("\nDetected DatasetForms:")
    for dataset in datasets:
        print(f"{dataset} -> {get_job_name(dataset)}")
    print("\nOperator action required: rerun the listed jobs in Airflow, one task at a time. This script made no rerun.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
