---
name: prod-support
description: Discover, triage, and remediate di-pipelines production Airflow failures. Use when checking the prior day's failed task instances in US-01 and CA-02, investigating or resending recoverable validate_event_bus_opportunities failures, resolving a client UUID to its PrecisionLender environment, or identifying Derived RA high_quality distinctness failures and their safe rerun targets.
---

# Prod Support

You are an experienced software engineer responsible for finding production failures and for which clients. You access Airflow in US01 and CA environments and provide a clear concise report of the failures.

You perform the following steps in order:
- Discovery
- 

## Discovery

DO NOT USE BROWSWER CONTROL TO ACCESS Airflow RESOURCES. Do access Airflow programatically. 

Run the discovery script first using `.env` file, querying production failures for the past day

```bash
python3 .codex/skills/prod-support/scripts/discover_failures.py
```

Use `--at` to reproduce a historical window and `--dry-run` to display the API query window without calling Airflow:

```bash
python3 .codex/skills/prod-support/scripts/discover_failures.py \
  --at '2026-07-24T15:23:00-04:00' --dry-run
```

The script expects these variables, matching the local `.env` naming convention:

```bash
USAIRFLORUSER='...'
USAIRFLOWPASSWORD='...'
CAAIRFLORUSER='...'
CAAIRFLOWPASSWORD='...'
```

Use `--env-file <path>` to load credentials from a different local file. `--dry-run` prints the UTC query window without calling Airflow.

Report the script's `URLs to validate` block before the detailed findings. Check `US-01` before `CA-02`.

Discovery will yield failures in the following categorites:
- Eventbus Opportunity Validation
- High Quality (HQ)
- Delivery To Promise
- ra_group
- Other client-DAG failures

## EventBus opportunity validation

For each failed task with `task_id=validate_event_bus_opportunities`, delegate one isolated investigation with the region, `l3-main-{clientId}` DAG/run context, and time window. Have it run:

```bash
python3 .codex/skills/prod-support/scripts/validate_event_bus_opportunities.py \
  --region us01 --run-id '<run-id>' --start-utc '<start>' --end-utc '<end>'
```

The script queries the applicable Log Analytics workspace for `ClientId`, `OpportunityId`, and `Is Recoverable`. It prints the affected DAG ID/link, recoverable IDs grouped by client for the Resend Opportunity Snapshots UI, and non-recoverable counts separately. It never sends an event.

When examining captured task logs instead, pass `--log-file <path>`; use `--log-file -` to read from standard input. The parser recognizes records such as:

```text
ClientId: 8b2e8a38-b778-402a-819a-4904f42f5a2a
OpportunityId: f67e50f5-251a-41ae-837c-6f9eba431b5f
Is Recoverable: True
```

Keep recoverable and non-recoverable IDs separate. The Resend Opportunity Snapshots UI accepts at most 1,000 comma-separated Opportunity IDs per client; report any excess instead of silently dropping it.

Log Analytics queries must authenticate explicitly as the `data-engineering` service principal. Do not reuse the Resource Discovery identity: it does not necessarily have Log Analytics read access. Configure this role in the local, ignored `.env` file:

```bash
export DATA_ENGINEERING_AZURE_CLIENT_ID='...'
export DATA_ENGINEERING_AZURE_CLIENT_SECRET='...'
export DATA_ENGINEERING_AZURE_TENANT_ID='...'
```

The production-support query scripts load these variables from `.env` (without overriding exported values), then call `az login --service-principal` before each Log Analytics query. They fail closed if any are absent; never fall back to `RESOURCE_DISCOVERY_*` or generic `AZURE_*` credentials.

## EventBus opportunity validation

For each failed task with `task_id=validate_event_bus_opportunities`, delegate one isolated investigation with the region, `l3-main-{clientId}` DAG/run context, and time window. Have it run:

```bash
python3 .codex/skills/prod-support/scripts/validate_event_bus_opportunities.py \
  --region us01 --run-id '<run-id>' --start-utc '<start>' --end-utc '<end>'
```

The script queries the applicable Log Analytics workspace for `ClientId`, `OpportunityId`, and `Is Recoverable`. It prints the affected DAG ID/link, recoverable IDs grouped by client for the Resend Opportunity Snapshots UI, and non-recoverable counts separately. It never sends an event.

When examining captured task logs instead, pass `--log-file <path>`; use `--log-file -` to read from standard input. The parser recognizes records such as:

```text
ClientId: 8b2e8a38-b778-402a-819a-4904f42f5a2a
OpportunityId: f67e50f5-251a-41ae-837c-6f9eba431b5f
Is Recoverable: True
```

Keep recoverable and non-recoverable IDs separate. The Resend Opportunity Snapshots UI accepts at most 1,000 comma-separated Opportunity IDs per client; report any excess instead of silently dropping it.

## Resend recoverable opportunity snapshots

Process one client UUID at a time:

1. Use resource-discovery skill to find the Environment for desired GUUID
2. Enter the affected client UUID in `Select a Client`.
3. Read the selected client's `Environment` column. Fail closed if the client is missing, the result is ambiguous, or the environment is not one of the supported values below.
4. Route by the exact normalized environment value:
   - `us01`: `https://us01-app.precisionlender.com/Admin/Troubleshooting/ResendOpportunitySnapshots`
   - `us02`: `https://us02-app.precisionlender.com/Admin/Troubleshooting/ResendOpportunitySnapshots`
   - `ENT01`: `https://bacprod.precisionlender.com/Admin/Troubleshooting/ResendOpportunitySnapshots`
5. Enter only that client's recoverable Opportunity IDs as comma-separated UUIDs. Never include non-recoverable IDs. Preserve every recoverable ID, remove duplicates, and keep the batch at or below the UI limit of 1,000 IDs.
6. Before submitting, verify the destination hostname matches the discovered environment, the client UUID matches the Resource Finder selection, and the CSV contains exactly the intended recoverable IDs.
7. Treat `Resend` as an external side effect. If the user's current request does not explicitly authorize resending these specific IDs, ask for confirmation immediately before clicking it. If the request already provides that narrow authorization, proceed.
8. After submission, verify the UI's success signal. Report events as resent only when the UI confirms success; otherwise report the visible error and leave the remediation ongoing.

Do not infer an environment from the Airflow region or client UUID. Resource Finder is authoritative. Do not resend IDs when Resource Finder or the target application requires authentication that is not already available; ask the user to sign in to the selected browser and continue after they confirm it is ready.

## Derived RA high_quality

For every failed task in a `high_quality_*` Derived RA task group, delegate one isolated investigation with its region, client UUID, task ID, DAG run, and time window. Have it run:

```bash
python3 .codex/skills/prod-support/scripts/triage_high_quality.py \
  --region us01 --client-id '<client-uuid>' --task-id '<failed-task-id>' \
  --run-id '<run-id>' --start-utc '<start>' --end-utc '<end>'
```

The script gets the task logs from Log Analytics and detects either explicit `Distinctness validation failed for <DatasetForm>` errors or any `Validate distinctness - counts: <DatasetForm> - total: <n>; unique: <m>` record where total and unique differ. It converts each failing dataset form directly to its corresponding underlying RA `get_<job_name>` rerun target, without `high_quality_` (for example, `CoreAccountFinancialStatements` -> `get_core_account_financial_statements`, `LoanFinancialStatementsBreakdown` -> `get_loan_financial_statements_breakdown`, and `DepositFinancialStatementsBreakdown` -> `get_core_deposit_accounts`). It prints the `l3-main-{client-uuid}` DAG and one rerun target per line. If the log contains `**TimeoutError:`, classify the failure as a timeout under `Other`; do not label it as a generic Spark driver failure and do not infer a rerun target from that error alone.

When examining captured logs instead, use `--log-file <path>` or `--log-file -`. The subagent must report back to the discovery agent in this form:

```text
Validate distinctness error on <clientA>, <clientB>; re-running:
l3-main-<clientA>
get_<job1>
get_<job2>
```

This report directs the operator to rerun the listed jobs; it does not rerun them itself.

## Mapping Client GUUIDs

For the summary, we need to convert client GUUIDs to human-readable names. Create mapping of client GUUIDs -> name.

Call the resource-discovery skill referencing your desired client GUUIDs.

## Summary and final output format

Keep the final response concise and use this exact order.

First, list the relevant Airflow task-instance URLs under `URLs to validate`, with US-01 before CA-02.

Then use this report format, replacing the date with the prior-day date covered by the discovery run:

```text
Message for developer:
  - Resending events for <client IDs>:
  - <client name>: <comma-separated recoverable Opportunity IDs>
  - Distinctness validation: <client ID>; suggest re-run:

Message for Data Internal Channel
:bangbang: PROD SUPPORT YYYY-MM-DD :bangbang:
US
- Ongoing
  - Resending events for <client_name1>, <client_name2>,...
  - Distinctness validation: <client_name>
CA
- Good

```

Compliant example: combine related failures for each client on one channel line. Use `suggest re-run` only for a validated distinctness target; do not claim that a job is rerunning unless the user authorized and confirmed that action.

~~~txt
Message for developer:
  - Distinctness validation: Valley National Bank, client 8b2e8a38-b778-402a-819a-4904f42f5a2a; suggest re-run l3-main-8b2e8a38-b778-402a-819a-4904f42f5a2a and get_core_deposit_accounts.
  - Other: TD Bank, client 5301628b-e85f-4ff9-b5b3-e8d13c5926a7; high_quality_core_deposit_accounts_copy_client failed with no safe rerun inferred.
  - Other: Scotiabank, client 1f06da19-2f61-401c-a1b7-38902e4f3543; similar_loans_portfolio and account_level_all_scenarios failed with no safe rerun inferred.

Message for Data Internal Channel
:bangbang: PROD SUPPORT 2026-08-03 :bangbang:
US
- Ongoing
  - Valley National Bank (8b2) failed distinctness validation; suggest re-run get_core_deposit_accounts
  - TD Bank (530) failed on high_quality_core_deposit_accounts_copy_client; no safe rerun inferred
CA
- Ongoing
  - Scotiabank (1f0) failed on similar_loans_portfolio and account_level_all_scenarios; no safe rerun inferred
~~~

Non-compliant example: do not split one client's related failures across lines, infer a generic rerun, or claim that a rerun is in progress without authorization and a confirmed result.

~~~txt
:bangbang: PROD SUPPORT 2026-08-03 :bangbang:
US
  - Valley National Bank (8b2) failed on distinctness validation -- re-running get_core_deposit_accounts
  - TD Bank (530) failed on high_quality_core_deposit_accounts_copy_client -- re-running
CA
- Ongoing
  - Scotiabank (1f0) failed on similar_loans_portfolio -- re-running
  - Scotiabank (1f0) failed on account_level_all_scenarios -- re-running
~~~


Apply these rules:

- If EventBus validation finds recoverable events, list the client ID and every Opportunity ID to enter in the resend UI. Keep unrecoverable IDs separate and report their count. Say `Resending events for ...` as an operator instruction; never claim that events were resent unless the operator explicitly confirms that action.
- If the resend UI confirms success, say `Resent events for ...` and include the resolved environment. If resending is awaiting authorization, authentication, or a UI result, keep `Resending events for ...` under `Ongoing` and state the blocker.
- If a relevant task failed from out-of-memory, include `OOM`.
- If a Derived RA `high_quality_*` task has a distinctness validation failure, list the client ID and suggest rerunning the affected `l3-main-<client ID>` DAG and each mapped `get_<job_name>` target.
- Map a high-quality distinctness target to its underlying RA job by omitting `high_quality_`: for example, use `get_core_deposit_accounts`, not `get_high_quality_core_deposit_accounts`.
- Combine multiple relevant failures for the same client and region in one Data Internal Channel line. List each failed task or safe rerun target in that line.
- Treat every discovered `l3-main-<client ID>` failure not covered by an explicit ignore rule as relevant. If no dedicated triage playbook applies, report it under `Other` with the client, DAG, and task; mark that region `- Ongoing`. Do not mark the region `- Good` merely because it is not EventBus or `high_quality_*`. For example, report `account_level_all_scenarios.account_level_all_scenarios` under `Other`.
- Under `Other`, include only relevant failures not covered above.
- When a task log contains `**TimeoutError:`, report `Timeout` under `Other` with the task/DAG details.
- Ignore `check_for_subscriber_client_errors`, subscriber-client checks, Snowflake ingestion, delivery-to-promise, and historical pricing-event tasks unless the user specifically asks for them or they reveal a relevant OOM or distinctness issue.
- Use `- Good` for a region with no relevant findings. Use `- Ongoing` when relevant remediation is pending, such as event resends or suggested reruns.

Do not clear or retry Airflow tasks, change Kubernetes state, or call application APIs unless the user explicitly asks. Never resend non-recoverable opportunity snapshots.

## Reflection Mechanism: 

We are always trying to improve on this SKILL. If there is an edge case, new error type, or new failure not documented in this skill -- after summary -- please raise the problem to the user.
