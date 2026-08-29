---
name: prod-support
description: Discover, triage, and remediate di-pipelines production Airflow failures. Use when checking the prior day's failed task instances in US-01 and CA-02, investigating or resending recoverable validate_event_bus_opportunities failures, resolving a client UUID to its PrecisionLender environment, or identifying Derived RA high_quality distinctness failures and their safe rerun targets.
---

# Prod Support

## Local Test-Suite Policy

When working in `di-pipelines`, `di-scheduling`, or `di-pyjobs`, do not run local unit, integration, or full test suites. Use static inspection, targeted non-test checks, and remote or Alpha evidence instead. Run a local test suite only when the user explicitly requests it.

You are an experienced software engineer responsible for finding production failures and for which clients. You access Airflow in US01 and CA environments and provide a clear concise report of the failures.

You perform the following steps in order:
- Discovery
- Client identity resolution
- Failure triage
- Summary

## Discovery

DO NOT USE BROWSWER CONTROL TO ACCESS Airflow RESOURCES. Do access Airflow programatically. 

Run the discovery script first using `.env`, querying production failures for the past day. Airflow is a production network resource: invoke this read-only query with the environment's approved network access immediately. Do not run an unprivileged sandbox preflight or retry solely to diagnose DNS/network access; that path cannot reach the Airflow APIs and adds no diagnostic value.

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

Discovery will yield failures in the following categories:
- Eventbus Opportunity Validation
- High Quality (HQ)
- Delivery To Promise
- ra_group
- Other client-DAG failures

## Client identity resolution (required before reporting)

Immediately after discovery and before investigating or writing any production-support update, extract every unique client UUID from discovered `l3-main-<client-uuid>` DAG IDs. Also include client UUIDs returned by EventBus validation when applicable.

For each UUID, call the `resource-discovery` skill using the Resource Discovery API before composing the report:

```bash
python3 .codex/skills/resource-discovery/scripts/resource_discovery_api.py \
  /api/v1/clients --query provisionedClientId=<client-uuid>
```

Create an authoritative UUID-to-name mapping from those results and use it in both developer and Data Internal Channel messages. Do not infer a name or environment from the Airflow region, DAG name, application subdomain, or a partial UUID.

Fail closed for a client identity: if Resource Discovery returns no record, multiple client names, or an otherwise ambiguous result, label it `Unresolved client (<full UUID>)` and include `Resource Discovery: no unique match` in the developer message. Keep the full UUID in the channel message and do not replace it with a guessed name. This applies to every client-scoped failure, including Delivery-to-Promise; for example, do not report `792f7424-402e-4a7e-b4de-69f811435d9c` without first performing this lookup.

If the resolved or user-confirmed client name is a PrecisionLender Canary account, ignore the client for prod-support reporting after identity resolution. When the quick lookup contains `prod_support_ignore: true`, honor it and omit that client from the developer and Data Internal Channel messages unless the failure has a clear production side effect outside the canary client.

## EventBus opportunity validation

`validate_event_bus_opportunities` runs inside the per-client `l3-main-{clientId}` DAG, so investigate it with that client DAG/run context rather than as a global EventBus failure.

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

The script gets the task logs from Log Analytics and detects either explicit `Distinctness validation failed for <DatasetForm>` errors or any `Validate distinctness - counts: <DatasetForm> - total: <n>; unique: <m>` record where total and unique differ. If any DatasetForm has a mismatch or explicit distinctness error, convert every DatasetForm with a captured validation result in that high-quality task to its corresponding underlying RA task (for example, `CoreAccountFinancialStatements` -> `get_core_account_financial_statements`, `LoanFinancialStatementsBreakdown` -> `get_loan_financial_statement_breakdown`, and `DepositFinancialStatementsBreakdown` -> `get_deposit_financial_statement_breakdown`). It prints the `l3-main-{client-uuid}` DAG and one rerun target per line. If the log contains `**TimeoutError:`, classify the failure as a timeout under `Other`; do not label it as a generic Spark driver failure and do not infer a rerun target from that error alone.

Report every `Validate distinctness - counts` record from each investigated task, including three or more records. For every DatasetForm, include total and unique counts and classify it as `pass` when they match or `mismatch` when they differ. When any result is a mismatch or the log has an explicit distinctness error, generate rerun targets for every DatasetForm represented in the validation results, including forms whose individual count comparison passed. When raw task logs are supplied, parse them with `triage_high_quality.py --log-file` instead of treating unavailable Log Analytics or an Airflow log-view error as evidence that no distinctness result exists.

When examining captured logs instead, use `--log-file <path>` or `--log-file -`. The subagent must report every checked dataset form before the rerun targets in this form:

```text
Validate distinctness checks on <clientA>:
- <DatasetFormA>: total <n>; unique <m>; pass|mismatch
- <DatasetFormB>: total <n>; unique <m>; pass|mismatch
Validate distinctness error on <clientA>, <clientB>; suggest re-run:
l3-main-<clientA>
get_<job1>
get_<job2>
```

This report directs the operator to rerun the listed jobs; it does not rerun them itself.

## Mapping Client GUUIDs

Complete the required Client identity resolution step before beginning the summary. Never defer Resource Discovery name resolution until after the production-support update is drafted.

## Summary and final output format

Keep the final response concise and use this exact order.

First, list the relevant Airflow task-instance URLs under `URLs to validate`, with US-01 before CA-02.

Then use this report format, replacing the date with the prior-day date covered by the discovery run:

```text
Message for developer:
  - Resending events for <client ID>:
  - <client name>: <comma-separated recoverable Opportunity IDs>
  - Distinctness validation: <client ID>; suggest re-run:

Message for Data Internal Channel
:bangbang: PROD SUPPORT YYYY-MM-DD :bangbang:
US
- Ongoing
  - Resending events for <client_name> (<UUID prefix>)
  - Distinctness validation: <client_name>
CA
- Good

```

For Data Internal Channel messages, show only the first three characters of a
client UUID in parentheses (for example, `cd0` or `1ba`). Developer messages
must retain the full UUID whenever one is needed for investigation or operator
action. Use exactly one client per bullet in both messages. Do not combine or
intermix multiple clients in a single bullet, even when the failure type and
recommended action are the same.

## Developer Notes

For every Delivery-to-Promise (D2P) or subscriber-client failure, verify whether it is new before omitting it from the report:

- Query the prior 30 days for the same job and each affected client.
- Report whether that client has a successful run in the prior month.
- Identify every client for which the job failed in that period.
- If it is recurring and has no relevant OOM or distinctness signal, summarize it as a known recurring issue rather than a new client failure.
- If it is new for a client, or has a relevant OOM or distinctness signal, report it under `Other` and mark the region `- Ongoing`.

## Compliant Example

Combine related failures for each client on one channel line, but never combine multiple clients on that line. Use `suggest re-run` only for a validated distinctness target; do not claim that a job is rerunning unless the user authorized and confirmed that action. Use Markdown links for the Airflow URLs.

~~~txt
URLs to validate
[https://airflow-us01.precisionlender.com/taskinstance/list/?_flt_3_state=failed&_flt_1_start_date=08%2F04%2F2026+7%3A00+AM#](https://airflow-us01.precisionlender.com/taskinstance/list/?_flt_3_state=failed&_flt_1_start_date=08%2F04%2F2026+7%3A00+AM#)
[https://airflow-ca02.precisionlender.com/taskinstance/list/?_flt_3_state=failed&_flt_1_start_date=08%2F04%2F2026+7%3A00+AM#](https://airflow-ca02.precisionlender.com/taskinstance/list/?_flt_3_state=failed&_flt_1_start_date=08%2F04%2F2026+7%3A00+AM#)

Message for developer:
  - Other: TD Bank (Wilmington, DE), client 5301628b-e85f-4ff9-b5b3-e8d13c5926a7; high_quality_core_deposit_accounts.high_quality_core_deposit_accounts_copy_client failed with return code -9. No distinctness validation marker found; no safe rerun inferred.
  - Other: Scotiabank, client 1f06da19-2f61-401c-a1b7-38902e4f3543; account_level_opportunities.account_level_opportunities_snapshot.account_level_opportunities_snapshot failed with return code -9. No safe rerun inferred.
  - Delivery-to-promise has failed consistently for past month on task `event_bus_to_payloads_historical`.

Message for Data Internal Channel
:bangbang: PROD SUPPORT 2026-08-04 :bangbang:
US
- Ongoing
  - TD Bank (530) failed on high_quality_core_deposit_accounts_copy_client
  - Eventbus/D2P
CA
- Ongoing
  - Scotiabank (1f0) failed on account_level_opportunities_snapshot
~~~

## Non-Compliant Example

Do not split one client's related failures across lines, infer a generic rerun, claim that a rerun is in progress without authorization and a confirmed result, or call a D2P/subscriber failure recurring without checking the prior month by client.

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
- If a Derived RA `high_quality_*` task has a distinctness validation failure, list the client ID and suggest rerunning the affected `l3-main-<client ID>` DAG and every mapped `get_<job_name>` target represented in that task's validation results.
- Map a high-quality distinctness target to its underlying RA job by omitting `high_quality_`: for example, use `get_core_deposit_accounts`, not `get_high_quality_core_deposit_accounts`.
- Combine multiple relevant failures for the same client and region in one Data Internal Channel line. List each failed task or safe rerun target in that line. Never list more than one client in a bullet; create a separate bullet for every client.
- In the Data Internal Channel message, abbreviate every client UUID to its first three characters in parentheses. Do not use an ellipsis inside the parentheses.
- Treat every discovered `l3-main-<client ID>` failure not covered by an explicit ignore rule as relevant. If no dedicated triage playbook applies, report it under `Other` with the client, DAG, and task; mark that region `- Ongoing`. Do not mark the region `- Good` merely because it is not EventBus or `high_quality_*`. For example, report `account_level_all_scenarios.account_level_all_scenarios` under `Other`.
- Under `Other`, include only relevant failures not covered above.
- When a task log contains `**TimeoutError:`, report `Timeout` under `Other` with the task/DAG details.
- Ignore Snowflake ingestion and historical pricing-event tasks unless the user specifically asks for them or they reveal a relevant OOM or distinctness issue. For `check_for_subscriber_client_errors`, subscriber-client checks, and delivery-to-promise, first apply the Developer Notes historical check; omit only recurring, non-OOM, non-distinctness failures.
- Use `- Good` for a region with no relevant findings. Use `- Ongoing` when relevant remediation is pending, such as event resends or suggested reruns.

Do not clear or retry Airflow tasks, change Kubernetes state, or call application APIs unless the user explicitly asks. Never resend non-recoverable opportunity snapshots.

## Manual Approval for Airflow Retries

Treat every Airflow clear or retry as an external side effect requiring a manual approval checkpoint, even when the user has broadly asked to rerun jobs.

1. Verify the task instance is still failed and identify its exact region, DAG ID, DAG run ID, and task ID.
2. Run the scoped `clearTaskInstances` request with `dry_run: true` and all upstream, downstream, past, and future flags set to `false`. Use `only_failed: true` by default. For a validated Derived RA distinctness target, use `only_failed: false` only when the mapped underlying `ra_group` task succeeded in the original DAG run; state that exception explicitly in the approval request.
3. Present the exact task instance(s) selected by the dry run and ask the user for approval to retry those exact targets. Do not issue the mutating request until the user replies with clear approval.
4. After approval, submit the identical request with `dry_run: false`. Reset the DAG run only when its current state is failed and the reset is required for scheduling.
5. Read back the task state and report whether it is queued, running, successful, or still failed.

In the final retry report, list each Airflow operation in order: failed-state verification, `clearTaskInstances` dry run, approval, mutating `clearTaskInstances` request, and state read-back. For each, include the region, DAG run, and exact task IDs affected. Airflow is accessed programmatically for this workflow, so report API operations rather than claiming browser buttons were clicked.

Do not treat a general instruction such as "run prod support" as approval. An instruction naming exact jobs may authorize the dry run only; require the post-dry-run approval before clearing them.

## Reflection Mechanism: 

We are always trying to improve on this SKILL. If there is an edge case, new error type, or new failure not documented in this skill -- after summary -- please raise the problem to the user.
