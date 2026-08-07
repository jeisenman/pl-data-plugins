---
name: datafinder
description: Find, inspect, create and explain PrecisionLender data locations across the local data-engineering repositories. Use when a request asks where a field, dataset, table, job, schema, DAG, resource, client data path, or pipeline behavior is defined or produced, especially across di-pipelines, di-pyjobs, di-schema-definitions, di-scheduling, and pl-application. Route primary Relationship Awareness (RA) questions to the RA finder and derived-dataset primary-source questions to the Primary finder subagent.
---

# DataFinder

## Local Test-Suite Policy

When working in `di-pipelines`, `di-scheduling`, or `di-pyjobs`, do not run local unit, integration, or full test suites. Use static inspection, targeted non-test checks, and remote or Alpha evidence instead. Run a local test suite only when the user explicitly requests it.

Find, create, and explain data for testing data-engineering changes. Prefer alpha data, then staging only when no suitable alpha data exists. Work with one client at a time and require non-null test data for every requested source or transformation.

## Client eligibility

Before running a data search for a candidate client, verify that the producing job
is available for that client. For an RA source, confirm the exact task in the
client's `l3-main-<client-guid>` Airflow DAG and, when the request concerns
current source data, confirm it has a recent successful run. For primary or
derived sources, confirm the corresponding producer task is present and enabled
in that client's DAG. Search only clients that pass this check.

Do not treat the presence of a repository task definition, a client-specific
resource override, or a preferred-client listing as evidence that the job runs
for that client. If availability cannot be verified because Airflow access is
unavailable, say so and do not claim the client has data. Record the job/task,
client GUID, evidence used, and availability result before reporting any ADLS
search result.

Accept a specific request or a Jira key in the form `DE-####`. Common requests include adding, re-sourcing, or recalculating fields in primary, derived, or reporting datasets.

Do use gitworktrees with the pattern `repositories/di-pipelines/DE-####`. If branch exists re-fetch and pull. 

Do not use `gh` or `git force` commands that erase auditability,

## Preferred Alpha Clients

1. First Developer Bank: `32743a57-2030-4fa5-aadd-756ade802493`
   - Airflow: `https://airflow.alpha01.precisionlender.com/dags/l3-main-32743a57-2030-4fa5-aadd-756ade802493/grid`
   - PL Application: `https://application.beta01.precisionlender.com/Admin/Clients/32743a57-2030-4fa5-aadd-756ade802493`
2. First Example Bank: `99b9412b-70fd-4221-8431-d1b3934889ec`
   - Airflow: `https://airflow.alpha01.precisionlender.com/dags/l3-main-99b9412b-70fd-4221-8431-d1b3934889ec/grid`
   - PL Application: `https://application.staging.precisionlender.com/Admin/Clients/99b9412b-70fd-4221-8431-d1b3934889ec`

## Definitions
- Primary: a copied dataset from an external source, such as from a database, ADLS file, or API
- Derived: a dataset created by joining and transforming 1 or more primary or derived datasets to make a data engineering understandable table
- Reporting: dataset given to clients

## RA finder

For requests involving primary Relationship Awareness (RA), delegate the investigation to the `RA finder` subagent defined at `.codex/agents/ra-finder.toml`.

The RA finder searches these areas first:

- `repositories/**/di-pipelines/ra-jobs/` for the standalone RA job package.
- `repositories/**/di-pipelines/de-jobs/src/datamart/jobs/ra/` for RA ingestion and transformation jobs.
- `repositories/**/di-pipelines/dags/precisionlender/dags/task_groups/main/ra_jobs.py` for primary RA orchestration.
- `repositories/**/di-pipelines/dags/precisionlender/dags/task_groups/derived/` for derived and monthly RA datasets.
- `repositories/**/di-pipelines/de-jobs/src/datamart/jobs/cross_client/data_dictionary.py` for dataset descriptions and published data contracts.

The agent must complete these steps.

1. Find the primary dataset's relative path and task definition. Capture the task symbol, `raFile`, `raDirectory`, input resource, output resource, and path conventions.

For example, `dbStagingTreasuryFinancialStatementBreakdowns.csv` is defined in `dags/precisionlender/dags/task_groups/main/ra_jobs.py`:
~~~python
get_treasury_financial_statement_breakdown = OperatorFactory(
    dag=dag,
    job_name='get_treasury_financial_statement_breakdown',
    job_reference='datamart.jobs.ra.treasury_financial_statement_breakdown.to_datamart.GetTreasuryFinancialStatementBreakdown',
    override_activity_args={
        'dataset': 'PL_RelationshipAwareness/Core/TreasuryFinancialStatementBreakdown',
        'datasetStage': 'Primary',
        'datasetVersion': 'v1.1',
        'chunkSize': '300000',
        'fileFormat': 'csv',
        'inputResource': 'OperationalADLS',
        'inputPathConvention': 'di_pyjobs.path.relationship_awareness.OperationalRA',
        'outputResource': 'HistoricalDataMartADLS',
        'outputPathConvention': 'di_pyjobs.path.data_studio.DataStudioHistorical',
        'raFile': 'DatabaseOutput/dbStagingTreasuryFinancialStatementBreakdowns.csv',
        'raDirectory': ra_directory_template,
        'raVersion': ra_version_template,
        'windowStart': window_start,
        'windowEnd': window_end,
        'datastores': 'HistoricalDataMartADLS,OperationalADLS,OMSLoggingApi',
        'name': 'GetTreasuryFinancialStatementBreakdown',
    },
    package_archive=DE_JOBS_ARCHIVE_PATH,
    override_operator_args=TREASURY_FINANCIAL_STATEMENT_BREAKDOWN_ARGS.args(client_id=client_id, backfill=backfill),
).operate(compute=TREASURY_FINANCIAL_STATEMENT_BREAKDOWN_ARGS.compute(client_id=client_id, backfill=backfill))
~~~

2. Find a non-null example of the task's `raFile`. Use the task definition's exact `raFile` value and the requested columns:

In Codex, request Azure-enabled execution before running `ra.sh`. The script uses `az ... --auth-mode login`, and Azure CLI writes command and session state to `${AZURE_CONFIG_DIR:-$HOME/.azure}`. A restricted sandbox cannot write that directory and will fail with `PermissionError` before querying ADLS. Do not run an unprivileged preflight first, treat that error as missing data, or redirect/copy Azure credentials to another directory.

`ra.sh` requires the current Azure CLI Data Engineer user and rejects service-principal logins. Authenticate with `az login --use-device-code` before running it; do not put personal credentials in environment variables or files.

```bash
scripts/ra.sh find \
  --ra-file 'DatabaseOutput/<task-raFile>.csv' \
  --column '<desired-column>' \
  --column '<another-column>'
```

`ra.sh` searches DataIngress RA runs from the previous 14 days, downloads candidates to a temporary directory, and retains only the matching request/run locally. It reports the local directory and the client Airflow graph when it finds a row with non-null values for every requested column.

The subagent must report:

a. The requested dataset, fields, or behavior, and the Azure Storage Browser link for the operational ADLS searched. For First Developer Bank, use `https://portal.azure.com/#@precisionlender.com/resource/subscriptions/cde221ff-e7f4-4d39-be20-6f9d532cab60/resourceGroups/pl-group-us-adls2-preprod/providers/Microsoft.Storage/storageAccounts/pladls2uspreprod/storagebrowser`.
b. The local directory and file retained by `ra.sh`.
c. The producing job or task, including its symbol or task-group name when available.
d. Relevant schema, metadata, DAG, and downstream publication paths.
e. Search evidence, with exact file paths and line references where possible.
f. Any ambiguity between similarly named RA sources and the identifier needed to resolve it.

Keep RA investigations read-only unless the user separately requests an implementation change.

## Primary finder

For a derived-dataset request that starts from primary metadata, delegate the primary-data investigation to the `Primary finder` subagent defined at `.codex/agents/primary-finder.toml`.

The Primary finder must:

- Accept the derived dataset, its transformation, the primary metadata class or dataset, and the requested new fields as inputs.
- Locate the primary dataset's metadata, producer, task definition, exact ADLS path, and relevant transformation inputs.
- Recognize which requested fields are new and which primary dataset each field belongs to. Do not treat a field as available merely because it appears in derived metadata or a downstream schema.
- Convert each primary metadata class into its `DataStudioHistorical` path using `PATH_STAGE`, `PATH_PROVIDER`, `PATH_GROUP`, `DATASET_NAME`, and `LATEST_*_VERSION`. Do not search `DataIngress` for this step.
- Use the exact client tier when searching ADLS: alpha clients use storage account `pladls2usdatamartalpha01`; staging clients use `pladls2usdatamartprodt`. Primary Data Studio datasets use the `l3-historical` filesystem unless repository evidence specifies another resource.
- Search read-only and request Azure-enabled execution before using Azure CLI. Do not treat an authentication or permissions failure as evidence that data is absent.
- Inspect the transformation's explicit projections, joins, filters, casts, aggregations, and null-handling logic.
- Produce a test-data hypothesis in this form: `The new field(s) will appear in [derived_dataset] if [these primary fields] are non-null in [primary_dataset(s)] and [transformation conditions] hold.`
- Validate the hypothesis against a non-null ADLS example whenever access is available. If validation is unavailable, label the result as a hypothesis and state exactly what remains unverified.

Use `python3 -B scripts/primary.py`, not `scripts/ra.sh`, for primary Data Studio datasets. Pass one `--metadata FILE:CLASS` or explicit `--dataset ALIAS=PROVIDER/GROUP/NAME@vX.Y` per primary dataset and one repeatable `--column ALIAS:COLUMN` per required field.

Resolve paths without Azure access first:

```bash
python3 -B scripts/primary.py resolve \
  --client '<client-guid>' \
  --environment alpha \
  --metadata '<metadata-file.py>:<MetadataClass>' \
  --column '<MetadataClass>:<FieldName>'
```

Then request Azure-enabled execution and find shared non-null values within each dataset:

```bash
python3 -B scripts/primary.py find \
  --client '<client-guid>' \
  --environment alpha \
  --metadata '<metadata-file.py>:<MetadataClass>' \
  --column '<MetadataClass>:<FieldName>' \
  --column '<MetadataClass>:<AnotherFieldName>'
```

`primary.py find` uses the current Azure CLI Data Engineer user with `--auth-mode login`; it refuses a service-principal login. Authenticate with `az login --use-device-code` before running it. Do not place personal credentials in environment variables or files.

For multiple primary inputs, repeat both `--metadata`/`--dataset` and `--column`. The script proves that each dataset has a row where all of its requested columns are non-null; it does not prove cross-dataset join compatibility. Validate join keys and transformation filters separately.

The subagent must report the datasets and fields, client tier and storage account, ADLS path, field availability, transformation conditions, hypothesis, validation status, exact evidence paths/lines, and ambiguities.

Keep Primary finder investigations read-only unless the user separately requests an implementation change.


## RA Data Creator

TODO


## Primary Ingestion

Primary ingestion involves bringing new fields into our primary datasets. This step is dependent



## Creating PR:
```[txt]
We test our changes to our repository in alpha
```
