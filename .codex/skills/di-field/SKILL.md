---
name: di-field
description: This skill helps data engineers bring dataset fields end to end from primary ingestion, to derived dataset calculations, to Databricks/DBX, and Snowflake
metadata:
  scope:
    - "worktrees/di-pipelines/ds-jobs/src/datascience_jobs/meta_data/datasets/**/*.py"
    - "worktrees/di-pipelines/ds-jobs/src/datascience_jobs/utils/schemas/datamart/**/*.py"
    - "worktrees/di-pipelines/ds-jobs/src/datascience_jobs/jobs/primary_ingestion/**/*.py"
    - "worktrees/di-pipelines/ds-jobs/src/datascience_jobs/jobs/data/**/*.py"
    - "worktrees/di-pipelines/ds-jobs/src/datascience_jobs/jobs/reports/**/*.py"
    - "worktrees/di-pipelines/ds-jobs/src/datascience_jobs/jobs/dispatch/**/*.py"
    - "worktrees/di-pipelines/de-jobs/src/datamart/jobs/ra/**/to_datamart.py"
    - "worktrees/di-pipelines/de-jobs/src/datamart/jobs/snowflake/evolutions/**/*.py"
    - "worktrees/di-pipelines/de-jobs/src/datamart/jobs/snowflake/metadata/**/*.py"
    - "worktrees/di-pipelines/de-jobs/src/datamart/jobs/snowflake/repeatable/**/*.py"
    - "worktrees/di-pipelines/dags/precisionlender/dags/**/*.py"
    - "worktrees/di-schema-definitions/datasets/**/config.ini"
    - "worktrees/di-schema-definitions/datasets/**/v*/schema.json"
    - "worktrees/di-schema-definitions/datasets/**/v*/{alpha,prod}/**/*.sql"
    - "worktrees/di-schema-definitions/datasets/**/views/{alpha,prod}/**/*.sql"
  type: engineering-rule
---

# DI Field

## Local Test-Suite Policy

When working in `di-pipelines`, `di-scheduling`, or `di-pyjobs`, do not run local unit, integration, or full test suites. Use static inspection, targeted non-test checks, and remote or Alpha evidence instead. Run a local test suite only when the user explicitly requests it.

## Scope

- The authoritative scope is the frontmatter `metadata.scope` field.
- Apply this skill when a matched file changes a dataset field contract or one of its direct consumers.
- Read contracts and source data from adjacent worktrees as needed, but do not modify them for this workflow.
- Flag any required implementation change outside the frontmatter scope to the developer before editing it.

## Definitions
- Primary Ingestion: bring data from outside databases, data lakes, or APIs into data engineering ADLS/Snowflake
- Derived: transforms primary datasets into data engineer readable datasets
- Snowflake: creates schema definitions to copy data from ADLS to Snowflake environment
- Databricks: creates schema definitions to copy data from ADLS to Databricks environment

## Workflow
Run `scripts/update-worktrees.sh`
Data within di-pipelines flows in the following stages:
0. Create worktree branch
1. Primary Ingestion
2. Derived Datasets
3. DBX/Databricks, Snowflake, and data library

- If task only mentions downstream datasets, check that columns exist in derived. 
- If not included in derived, check that column exists in primary. 
- If column not exists in primary, use the datafinder skill to find representative data. Also use pl-contract skill to look inside of pl-application contracts to find relevant column
- If column does not exist in primary, and datafinder skill doesn't find representative data, then use data-creator skill to create data.
- If ticket says major version upgrade or entails dropping/re-naming a column, then FLAG to DEVELOPER IMMEDIATELY!

Upon seeing ticket, breakdown and re-order tasks from primary ingestion, to derived, to DBX/Snowflake/Data Library (L3).

## Primary Ingestion
Identify the primary dataset(s) that must be changed. Document the source dataset and the relevant fields.

This step involves:
a) Validate that primary dataset does not have the requested field(s)
b) Use the pl-contract skill to validate that the field(s) exist in source dataset
c) Use data finder skill to find data in relevant data sources
d) (Optional) if data does not exist, use datacreator skill to generate data 
e) Identify `class [datasetname]MetaData`. Add field to dataset
f) Complete steps a-e until no more primary datasets need to be adjusted.
g) After validation passes, prepare the ticket branch and the commit message `Add [field1, field2] to [dataset1]`, then hand off all staging, committing, worktree refresh, dead-code checks, pushing, and draft-PR creation to `github:yeet`. Do not push directly from this skill.
h) Give `github:yeet` the repository's `pull_request_template.md` with its placeholders replaced by a ticket-specific description. Check only checklist items supported by evidence; leave unperformed Alpha, integration, copy-log, data-explorer, scheduling, and changelog items unchecked.

For the PR description:
- State the ticket link, affected dataset(s), added field(s), source file/table, and whether the change is additive or breaking.
- Add subheader for `Testing`. Use datafinder skill to get relevant paths. The description should read:
    - We test our changes in alpha for [client-guuid] on [date]. Give URL to Azure Portal of data. 
    
### Primary metadata schema changes

When adding fields to a primary ingestion metadata class, preserve the class's existing schema style. Most simple primary metadata classes define one `_schema = StructType([...])` inside `_schema_vN`; for those, add the new `StructField(...)` entries directly inside that existing `StructType` block and update only the required version constant(s).

Compliant:
- Add new fields directly inside the existing `_schema = StructType([...])` block when the class already uses that style.
- Bump `LATEST_MINOR_VERSION` and matching DAG `datasetVersion` only when the path/version should move forward for the additive primary schema.
- Keep the diff scoped to the source mover, primary metadata schema, and orchestration version references needed for the requested field.

Non-compliant:
- Refactor a simple primary metadata class into `_v1_0_fields`, `_v1_1_fields`, or `_v1_2_fields` helper sections solely to add fields.
- Introduce new schema composition patterns unless the class already uses that pattern or the requested change genuinely requires version-specific schema behavior.
- Change unrelated dataset versions while bulk-editing repeated `datasetVersion` lines.

## Derived Datasets

For each requested field:

a) Identify the derived dataset and transformation job.
b) Confirm the field exists in the upstream primary or derived input. Determine if you need primary datafinder. If we have added a field to primary in the current worktree and we know non-null data exists, the field may not currently exist in ADLS. If necessary, use the datafinder Primary finder to resolve primary metadata to ADLS, find a non-null example, and state the conditions under which the field reaches the derived output.
c) Add the field to the transformation's explicit projection or mapping.
d) Document any rename, cast, join, aggregation, filtering, or deduplication.
e) Add the field to derived metadata and bump the minor version for additive changes.
f) Check inherited, monthly, or related derived datasets.
g) Update DAG dataset versions and downstream DBX/Snowflake consumers.
h) Add focused test coverage for source-to-derived projection and schema presence when applicable; do not run it locally unless the user explicitly requests it.
i) Identify required partition regeneration, backfill, or downstream reruns.

### Derived field naming and projection

Preserve the source-style field name unless the transformation declares an established alias. Represent every deliberate rename explicitly in the projection.

Compliant:

```python
CORE_DEPOSIT_ACCOUNT_COLS = [
    ("CoreBillableGroupAccountId",),
]
# Snowflake publication: CORE_BILLABLE_GROUP_ACCOUNT_ID
```

Non-compliant:

```python
CORE_DEPOSIT_ACCOUNT_COLS = [
    ("CoreBillableGroupAccountId", "BillingAccount"),
]
# No field contract explains the alias.
```

Do not rely on metadata alone. A field must be present in both the transformation projection and the derived metadata. Classify generated schemas as active or stale, update active schemas, and verify that coupled monthly metadata inherits the field without duplicating it.

Compliant:

```text
primary metadata
  -> derived projection
  -> derived metadata
  -> inherited monthly metadata
  -> active generated schema parity test
```

Non-compliant:

```text
Derived metadata contains the field, but the transformation projection drops it
and the tracked generated schema has no ownership decision.
```

### Deprecated Core Deposit generated schemas

Do not update these deprecated generated schema modules:

```text
ds-jobs/src/datascience_jobs/utils/schemas/datamart/Derived/PL_RelationshipAwareness/Core/CoreDepositAccounts/v2/schema.py
ds-jobs/src/datascience_jobs/utils/schemas/datamart/Primary/PL_RelationshipAwareness/Core/CoreDepositAccounts/v2/schema.py
```

These modules are no longer consumed after the move to `DatasetDownloader`.
For Core Deposit field-contract changes, update the applicable metadata class
under `ds-jobs/src/datascience_jobs/meta_data/datasets/` and its active
producer/consumer surfaces instead.

Non-compliant:

```text
Add a field to either deprecated CoreDepositAccounts v2 schema.py module
because it appears to mirror the dataset contract.
```

### Derived versioning

For an additive nullable field, increment the derived minor version and update every writer, copy task, backfill, and publisher that selects its `VersionPartition`. Leave an upstream dataset version unchanged when its contract already contains the field. Make coupled monthly datasets inherit or import the owning derived version.

Compliant:

```python
class CoreTreasuryAccountsMetaData(DatasetMetaData):
    LATEST_MAJOR_VERSION = 2
    LATEST_MINOR_VERSION = 4

    @property
    def _schema_v2(self):
        return StructType(
            self._get_x_to_y_fields_for_major_version(2, 0, self.LATEST_MINOR_VERSION)
        )

dataset_version = "v2.4"
```

Non-compliant:

```python
class CoreTreasuryAccountsMetaData(DatasetMetaData):
    LATEST_MAJOR_VERSION = 2
    LATEST_MINOR_VERSION = 4

dataset_version = "v2.3"
```

Flag a rename, removal, incompatible type change, stricter nullability, positional reorder, or semantic change immediately. These require a new major version, coexistence or migration decisions, and tests for both supported major schemas.

### Historical data decision

A metadata or DAG version bump affects future writes only. State whether existing derived or monthly partitions require the new contract and list regeneration or reruns in dependency order.

Compliant:

```text
Historical decision: required.
Run the primary backfill for the original source date, rerun the derived task
group, then rerun the monthly dataset and downstream publishers.
```

Non-compliant:

```text
Historical decision: the minor-version bump updates old partitions automatically.
```

### Focused derived tests

Assert the field's name, type, nullability, contractual order, source-to-derived projection, and selected dataset version. Add downstream publication assertions when those surfaces change.

Compliant:

```python
field = derived_schema["CoreBillableGroupAccountId"]
assert field.dataType == StringType()
assert field.nullable is True
assert derived_schema.fieldNames().index(field.name) == expected_index
assert ("CoreBillableGroupAccountId",) in CORE_DEPOSIT_ACCOUNT_COLS
assert derived_dataset_version == "v2.4"
```

Non-compliant:

```python
assert "CoreBillableGroupAccountId" in derived_schema.fieldNames()
# Type, nullability, order, projection, and version consumers remain untested.
```


## Report
TODO

## Snowflake
TODO

## Databricks (DBX) SQL

Use this workflow after the source and derived contracts have been updated and
the new field is present in the target dataset's ADLS output. A DBX schema
change publishes that existing field; it does not create the field upstream.

### Add an additive DBX column

For a nullable, additive field in `worktrees/di-schema-definitions`:

1. Find `datasets/<dataset_name>/`, determine the matching major-version
   directory (for example, `v2`), and confirm the producer's field name,
   PySpark-compatible type, nullability, and order. Keep the source-style
   name in `schema.json`; the generated DBX SQL preserves that name.
2. Decide whether the DBX view must select a specific new minor partition. If
   it does, increment `[v<major>].static_minor_version` in `config.ini` to
   the same minor version written by the upstream derived dataset. Do not add
   a static minor version merely because a field is added when the dataset is
   intentionally configured to read all minor partitions.
3. Add the field, with its verified type, to
   `datasets/<dataset_name>/v<major>/schema.json`. Preserve the contractual
   field order. Additive fields normally belong at the end unless another
   positional contract requires a different location.
4. Check whether the field must be sanitized. If so, add it to
   `[external_table].sanitized_fields` in `config.ini` before generating
   views, following the DBX sanitization policy.
5. From the `di-schema-definitions` worktree, regenerate tracked SQL for both
   environments:

   ```bash
   python sql_utils/create_external.py --config <dataset_name> --version v<major> --execution-env prod
   python sql_utils/create_external.py --config <dataset_name> --version v<major> --execution-env alpha
   python sql_utils/create_view.py --config <dataset_name> --execution-env alpha
   python sql_utils/create_view.py --config <dataset_name> --execution-env prod
   ```

   These generators update external-table and repair SQL for configured base
   and isolated stacks, then update their corresponding views. Do not hand-edit
   generated SQL except to correct the generator inputs or an established
   stack-specific view exception.
6. Inspect the generated diff. The column must occur in every applicable
   `create_external_table_*.sql`, and in every applicable view `SELECT`
   projection (including client-specific/sanitized views). Confirm the view's
   `VersionPartition` predicate uses the intended static minor version when
   one is configured. Keep generated `repair_external_table_*.sql` changes
   produced by the generator.
7. Perform targeted non-test validation: verify the JSON is valid; search the
   generated SQL for the column in every expected environment/stack; and
   compare the selected `VersionPartition` with the upstream derived version.
   Do not run a local test suite unless explicitly requested. In the PR,
   record the upstream dataset/version, column type and sanitization decision,
   generators run, and Alpha DBX evidence when available.

Examples of this pattern are merged PRs #125 (minor-version pin, schema,
external tables, and views) and #134 (schema plus generated external tables
and views) in `precisionlender/di-schema-definitions`.


## Change Guidance

Before changing a field contract, compare the proposed schema with all known readers and writers. Call out required backfills, versioning, migration windows, and validation coverage. Keep any implementation scoped to the affected contract and its direct producers or consumers.
