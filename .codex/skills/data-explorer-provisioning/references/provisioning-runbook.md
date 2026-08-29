# Data Explorer client/org provisioning runbook

Source: [New Data Explorer Client/Org Provisioning Guide](https://qtwo.atlassian.net/wiki/spaces/DI/pages/16868413/New+Data+Explorer+Client+Org+Provisioning+Guide), authored by Michael Nguyen and updated January 26, 2026. This reference records the page content supplied from Confluence on August 24, 2026.

## Ordered procedure

1. Add the client to `DATA_EXPLORER_CLIENTS` in `di-pipelines/dag-utils/temp_data_products.py`.
   - Historical source link: <https://github.com/precisionlender/di-pipelines/blob/af818e72064e2e946beeba14070657e594d1da89/dag-utils/temp_data_products.py#L134>
2. Run `thoughtspot_sync_orgs` in Airflow.
   - Alpha link: <https://airflow.alpha01.precisionlender.com/dags/thoughtspot_sync_orgs/grid>
   - Expected effects: create the ThoughtSpot org; create org groups and roles; assign internal Q2 Advisory; update `PL_DATA_STUDIO.DATA_EXPLORER.TENANTS` with the PL-client-ID-to-org-ID mapping.
3. Add the client to `thoughtspot_beta_clients` in the correct `vars_{ENV}.tfvars` file in the GitLab Snowflake Terraform repository `pl-data-studio/infrastructure`.
   - Historical development-file link: <https://gitlab.com/q2e/it/terraform/snowflake/q2e/projects/pl-data-studio/infrastructure/-/blame/develop/vars_development.tfvars?ref_type=heads#L22>
4. Merge and run the GitLab pipeline.
   - Expected effects: create `PL_{PL_CLIENT_ID}` for row-level security; add the `sf-data-studio` Snowflake connection to the ThoughtSpot org.
5. Run `thoughtspot_setup_version_control` in Airflow.
   - Alpha link: <https://airflow.alpha01.precisionlender.com/dags/thoughtspot_setup_version_control/grid>
   - Expected effects: create an org content-deployment branch in <https://github.com/precisionlender/data-explorer-thoughtspot>; configure org version control through the ThoughtSpot API.
6. The guide lists `thoughtspot_sync_metadata_version_control`, but explicitly says this step is turned off and must be reworked.
   - Historical Alpha link: <https://airflow.alpha01.precisionlender.com/dags/thoughtspot_sync_metadata_version_control/grid>
   - Intended content source: `internal_development` for development orgs; `internal_staging` for staging or production orgs; deploy items tagged `Prod`.
   - Failure mode: rerunning template deployment replaced Advisory's client-specific changes with original templates.
   - Current requirement: manually copy templates to the new org. Any future automation must target only the new org and treat version-controlled content as provisioning-time templates rather than ongoing synchronization.
7. Add the client data to Snowflake.
   - Current limitation: Snowflake data is loaded only for ThoughtSpot client users.
   - Backfill ADLS staging with `qds_4990_backfill_snowflake`.
   - Alpha link: <https://airflow.alpha01.precisionlender.com/dags/qds_4990_backfill_snowflake/grid>
   - DAG source: <https://github.com/precisionlender/di-pipelines/blob/master/dags/precisionlender/dags/qds_4990_backfill.py>
   - Scope the backfill to the new client instead of backfilling all `SNOWFLAKE_BETA_CLIENTS` again.
   - Run `snowflake_ingestion` to load staged data into Snowflake.

## Known pain points and future direction

- Provisioning spans GitHub Airflow code and GitLab Snowflake Terraform infrastructure.
- The client list is duplicated; a central ThoughtSpot client list would reduce drift.
- GitHub and GitLab currently need cross-repository integration.
- A future orchestrating DAG could execute the required DAGs in order and, if feasible, trigger the GitLab pipeline.

## Policy note

PII is never permitted in Jira or Confluence.
