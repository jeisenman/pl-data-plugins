---
name: data-explorer-provisioning
description: Provision a new PrecisionLender Data Explorer/ThoughtSpot client organization from an assigned Jira ticket across di-pipelines, Snowflake Terraform, ThoughtSpot, and Airflow. Use when a ticket asks to onboard, enable, provision, or backfill a new Data Explorer client/org, including adding DATA_EXPLORER_CLIENTS or thoughtspot_beta_clients, synchronizing a ThoughtSpot org, configuring version control, or loading the client's initial Snowflake data. When no ticket is supplied, discover eligible open tickets assigned to the current Jeisenman user and select the single unambiguous candidate.
---

# Data Explorer Provisioning

Provision one client from one ticket while preserving an auditable checkpoint between repository changes and external executions. Read [references/provisioning-runbook.md](references/provisioning-runbook.md) before acting.

## Safety and source of truth

- Treat the Jira ticket as the request record and the linked Confluence guide as the procedural source.
- Never copy personally identifiable information into Jira, Confluence, branches, commits, logs, or reports. By default, stop when a ticket contains PII. If the user explicitly authorizes handling the ticket's existing PII for this provisioning request, use only the minimum contact detail needed by the target system; do not reproduce it in output or create a new record containing it.
- Work on exactly one client and one environment per invocation.
- Do not merge changes, run GitLab pipelines, trigger Airflow DAGs, or modify ThoughtSpot/Snowflake until the user explicitly authorizes that external action. A request to inspect or prepare a ticket authorizes read-only discovery and code preparation only.
- Verify each prerequisite from live state. Do not infer that a merged change, pipeline, DAG, org, role, connection, branch, or data load succeeded.
- Never run `thoughtspot_sync_metadata_version_control`. The source guide marks it disabled because it can overwrite client customizations.
- Do not invent the manual ThoughtSpot template-copy procedure. Report it as a required manual handoff unless an approved current procedure is supplied.
- Do not send email invitations or notifications while creating a ThoughtSpot user unless the user explicitly authorizes sending them. If the selected provisioning mechanism always sends an invitation, stop and disclose that constraint before executing it.

## 1. Select and validate the ticket

1. If the user supplies a Jira URL or key, use that ticket. Otherwise, list open tickets assigned to the current Jira user with:

   ```jql
   assignee = currentUser() AND statusCategory != Done ORDER BY updated DESC
   ```

   Use `currentUser()` instead of a hard-coded account identifier so the skill remains correct for the Jeisenman account after Jira account migrations.
2. Retain only items with a client-provisioning signal in the summary, description, comments, labels, components, or linked work: `Data Explorer Provisioning`, `new client`, `new org`, `onboard`, `DATA_EXPLORER_CLIENTS`, `thoughtspot_beta_clients`, `PL_DATA_STUDIO.DATA_EXPLORER.TENANTS`, or initial client backfill. Treat `Data Explorer`, `ThoughtSpot`, `tenant`, and `Snowflake` alone as context signals, not sufficient selection criteria; they can describe unrelated maintenance or automation work.
3. Select the ticket automatically only when one candidate remains. If multiple candidates remain, return a compact table of key, summary, status, and last update and ask the user to choose. If none remain, report that no eligible open ticket is assigned and request a ticket key or a broader selection instruction.
4. Resolve the selected Jira URL or key and read the full ticket, comments, and linked implementation details.

5. Extract and report:
   - ticket key and summary;
   - client display name;
   - canonical PL client ID used by pipeline configuration;
   - target environment;
   - requested completion criteria;
   - any existing branches, pull requests, pipelines, or prior runs.
6. Use the `resource-discovery` skill when the ticket lacks a canonical client identifier or the identifier/environment mapping is ambiguous.
7. Stop before mutation if the client ID, target environment, or request scope cannot be established unambiguously.
8. Search current GitHub, GitLab, Airflow, ThoughtSpot, and Snowflake state for prior provisioning. Classify each stage as `not started`, `in progress`, `complete`, or `conflicting`; resume from the first incomplete safe stage.

## Optional: add a ThoughtSpot user

Perform this only when the ticket and user explicitly request it. Confirm that the client ThoughtSpot org already exists, identify the intended group/role, and check whether the user is already a member. Use the minimum existing ticket contact detail required to create the account. Do not send an invitation or notification unless explicitly authorized. Record only a non-sensitive outcome: user added, target org, and assigned role/group.

## 2. Add the client to di-pipelines

1. Locate the active `di-pipelines` checkout and inspect the current default branch; do not rely on the historical line-number URL in the guide.
2. Create or reuse the ticket branch following repository conventions.
3. Add the canonical client ID to `DATA_EXPLORER_CLIENTS` in `dag-utils/temp_data_products.py`, preserving the list's current type, order, formatting, and deduplication conventions.
4. Run proportionate static checks and targeted validation allowed by repository policy. Do not run broad local test suites where the workspace policy prohibits them.
5. Present the diff and validation evidence. Commit, push, and open a review request only when authorized.
6. Wait for the change to be merged and deployed to the intended Airflow environment before proceeding to the org-sync DAG.

## 3. Synchronize the ThoughtSpot org

After authorization and deployment, trigger `thoughtspot_sync_orgs` in the correct Airflow environment for the ticket. Use the Alpha link in the reference only when Alpha is the intended environment.

Monitor the run to a terminal state and verify evidence for all expected effects:

- the ThoughtSpot org exists for the client;
- org user groups and roles exist;
- internal Q2 Advisory is assigned;
- `PL_DATA_STUDIO.DATA_EXPLORER.TENANTS` maps the PL client ID to the ThoughtSpot org ID.

Stop on partial success. Record the run URL, run ID, timestamps, and the first failing task instead of rerunning the whole DAG blindly.

## 4. Add the Snowflake Terraform client

1. Inspect the `pl-data-studio/infrastructure` GitLab repository and its current variable-file conventions.
2. Select the existing `vars_{ENV}.tfvars` file that exactly matches the ticket environment.
3. Add the canonical client ID to `thoughtspot_beta_clients`, preserving the current syntax, order, and deduplication conventions.
4. Prepare the ticket branch and show the focused diff. Commit, push, and open or merge a request only when authorized.
5. After merge authorization, run the GitLab pipeline and monitor it to completion.
6. Verify that the pipeline created the client-specific `PL_{PL_CLIENT_ID}` Snowflake role used for row-level security and added the `sf-data-studio` Snowflake connection to the ThoughtSpot org.

Do not continue if the pipeline fails or either expected side effect is absent.

## 5. Configure ThoughtSpot version control

After authorization, trigger `thoughtspot_setup_version_control` in the intended Airflow environment. Monitor it to completion and verify:

- a client/org branch exists in `precisionlender/data-explorer-thoughtspot`;
- the ThoughtSpot org has the expected version-control configuration.

Record the DAG run and resulting branch URL.

## 6. Handle initial content safely

Do **not** trigger `thoughtspot_sync_metadata_version_control`. It previously replaced client-customized content with the original template.

Create a manual handoff stating that approved templates must be copied into the new org. Include the client, org ID, environment, source template environment (`internal_development` for development; `internal_staging` for staging or production), and the ticket key. Continue only after an operator confirms the manual copy is complete or provides a current approved automation procedure.

## 7. Backfill and ingest Snowflake data

1. Inspect the current `qds_4990_backfill_snowflake` DAG definition and runtime interface before changing or running it.
2. Prove that the run is scoped to only the new client. Prefer a supported per-run parameter if one exists.
3. Do not permanently replace `SNOWFLAKE_BETA_CLIENTS` with a single client or merge a temporary one-client hack. If the DAG cannot be safely targeted, stop and propose a focused ticket-scoped code change for review.
4. After authorization, run the targeted backfill and verify the new client's output in the ADLS staging location.
5. Trigger `snowflake_ingestion` only after the staging output is complete. Monitor it to a terminal state and verify the client's rows are present in the intended Snowflake table with the expected tenant isolation.

## 8. Report completion

Return a compact stage table containing:

- stage and status;
- repository diff, PR/MR, or commit link;
- pipeline or Airflow run link and terminal result;
- created org ID, Snowflake role, version-control branch, and tenant mapping evidence;
- ADLS backfill and Snowflake ingestion evidence;
- manual template-copy confirmation;
- blockers, retries, and follow-up tickets.

Declare provisioning complete only when every stage has evidence. Otherwise state the exact next safe action.
