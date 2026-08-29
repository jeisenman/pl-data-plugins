---
name: di-field
description: Orchestrate scoped subagents that bring PrecisionLender dataset fields end to end through source resolution, primary ingestion, derived datasets, Databricks/DBX, Snowflake, and final versioning, compatibility, regeneration, and backfill decisions. Use for additive or breaking dataset-field work that crosses one or more of these pipeline stages.
---

# DI Field

## Local Test-Suite Policy

When working in `di-pipelines`, `di-scheduling`, or `di-pyjobs`, do not run local unit, integration, or full test suites. Use static inspection, targeted non-test checks, and remote or Alpha evidence instead. Run a local test suite only when the user explicitly requests it.

## Agent topology

Run the workflow through the `DI field orchestrator` role in
`.codex/agents/di-field-orchestrator.toml`. It uses `gpt-5.6-sol` with `low`
reasoning effort; `low` is the Codex configuration value for the requested light
setting. If the current agent is not that role and can delegate, hand the complete
request to it. The orchestrator coordinates work and performs the final
administrative decision pass; it does not edit implementation files itself.

Use these subagents and do not replace them with unscoped generic workers:

| Stage | Agent | Model | Runs when |
| --- | --- | --- | --- |
| Source and data discovery | `DI field source resolver` | `gpt-5.6-luna`, medium | Always |
| Data creation | `DI field data creator` | `gpt-5.6-terra`, medium | Only when discovery finds no representative non-null data |
| Primary ingestion | `DI field primary` | `gpt-5.6-terra`, medium | When the primary contract or producer needs a change |
| Derived dataset | `DI field derived` | `gpt-5.6-terra`, medium | When the derived contract or transformation needs a change |
| DBX publication | `DI field DBX` | `gpt-5.6-terra`, medium | When DBX publishes the affected dataset |
| Snowflake publication | `DI field Snowflake` | `gpt-5.6-terra`, medium | When Snowflake publishes the affected dataset |

The source resolver uses `$datafinder` and `$pl-contracts`. Its RA and Primary
finder delegates must use `gpt-5.6-luna` with medium reasoning. If it reports
`data_status = absent`, run the data creator with `$datacreator`. Treat access or
authentication failures as `unresolved`, not `absent`; do not create data for an
unresolved search.

## Scope contract

Resolve exactly one ticket `di-pipelines` worktree and, when DBX changes are
required, exactly one ticket `di-schema-definitions` worktree. Pass their absolute
paths to the applicable agents. Do not inspect or modify sibling ticket worktrees.
Pass the exact dataset, field list, and target client/environment with every handoff.

- Source resolver: read only the selected `di-pipelines` worktree's metadata,
  producer jobs, transformations, DAG tasks, RA data dictionary, and direct
  publication references. It may search `repositories/pl-application` only for
  exact field/contract identifiers and then follow their direct DTO, mapper,
  persistence, and writer chain. It may read the selected dataset directory in
  `di-schema-definitions` and use the `datafinder` scripts. It must not edit files.
- Data creator: read only the source resolver's direct contract/writer paths and
  the identified pipeline producer. Its only write surface is the explicitly
  confirmed non-production client UI record. Do not write source code, databases,
  APIs, fixtures, files, shared clients, or production resources.
- Primary: write only the selected worktree's identified primary metadata class,
  primary ingestion/source-mover job, exact primary DAG task/version reference,
  and focused tests mirroring those modules. Do not edit derived, DBX, or Snowflake
  surfaces.
- Derived: write only the selected worktree's identified derived transformation,
  derived metadata, active generated schema, exact derived/monthly DAG consumers,
  and focused tests mirroring those modules. Do not edit primary, DBX, or
  Snowflake surfaces.
- DBX: write only `<schema-worktree>/datasets/<target-dataset>/`,
  including its `config.ini`, matching major-version `schema.json`, and generated
  Alpha/prod external-table, repair, and view SQL. Do not edit SQL generators or a
  different dataset directory.
- Snowflake: write only the selected `di-pipelines` worktree's direct target files
  under `de-jobs/src/datamart/jobs/snowflake/{evolutions,metadata,repeatable}/`
  and focused tests for those files. Do not edit upstream producers, DBX files, or
  unrelated Snowflake objects.
- Orchestrator administration: read the combined diffs and direct readers/writers
  across those scopes. Do not edit implementation files during the final pass.

If a required change falls outside an agent's write scope, stop that agent and
return the exact path and reason to the orchestrator. The orchestrator must tell
the developer before expanding scope.

## Definitions
- Primary Ingestion: bring data from outside databases, data lakes, or APIs into data engineering ADLS/Snowflake
- Derived: transforms primary datasets into data engineer readable datasets
- Snowflake: creates schema definitions to copy data from ADLS to Snowflake environment
- Databricks: creates schema definitions to copy data from ADLS to Databricks environment

## Workflow

1. Run `scripts/update-worktrees.sh`, create or select one ticket worktree for
   each repository that will change, and record each absolute path. Preserve
   unrelated user changes.
2. Run `DI field source resolver`. Require a structured handoff containing source
   contract, lineage, representative-data status (`found`, `absent`, or
   `unresolved`), affected stages, exact paths, and compatibility classification.
3. If and only if data status is `absent`, run `DI field data creator`. Pause for
   user authorization before any support login or final UI save not already
   explicitly authorized. After creation, rerun source validation before coding.
4. Run `DI field primary` when required. Wait for it because Derived depends on
   the resulting primary contract and version.
5. Run `DI field derived` when required. Wait for it because publication depends
   on the resulting derived contract and version.
6. After the upstream contract is stable, run `DI field DBX` and `DI field
   Snowflake` concurrently. Their write scopes are disjoint. If only one surface
   consumes the dataset, skip the other with evidence.
7. Wait for both publication agents, inspect their results, and run the final
   administrative pass below. Do not publish or open a PR before it passes.
8. If the ticket requests a major version or entails a rename, removal,
   incompatible type change, stricter nullability, positional reorder, or semantic
   change, flag it to the developer immediately. Agents may investigate read-only,
   but must not implement the breaking change until the migration decision is
   confirmed.

## Primary Ingestion
Identify the primary dataset(s) that must be changed. Document the source dataset and the relevant fields.

This step involves:
a) Validate that primary dataset does not have the requested field(s)
b) Use the pl-contract skill to validate that the field(s) exist in source dataset
c) Use data finder skill to find data in relevant data sources
d) (Optional) if data does not exist, use datacreator skill to generate data 
e) Identify `class [datasetname]MetaData`. Add field to dataset
f) Complete steps a-e until no more primary datasets need to be adjusted.
g) Return changed paths, validation evidence, selected versions, and unresolved
   downstream effects to the orchestrator. Do not stage, commit, push, or open a
   PR from this stage.

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


## Snowflake

Run this stage only after the upstream source and derived contracts are stable.
The Snowflake agent must:

1. Identify the exact metadata, repeatable object, and evolution files that own or
   publish the target dataset. Do not infer ownership from a similarly named table.
2. Confirm the Snowflake column name, source field, type, nullability, order, and
   any sanitization or client-specific behavior against the derived contract.
3. Add an additive nullable column only to the direct owning objects. Preserve the
   existing naming and evolution style; do not refactor unrelated definitions.
4. Verify every applicable create/alter/evolution and repeatable view projection,
   including isolated-stack or client-specific variants.
5. Perform targeted static or generation checks without running a local test suite
   unless explicitly requested. Return changed paths, generated artifacts,
   selected versions, and Alpha evidence or remaining validation needs.

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

## Final administrative pass

After Primary, Derived, DBX, and Snowflake have completed or returned an
evidence-backed skip, the orchestrator must inspect the combined changes and issue
one administrative decision report:

1. **Versioning:** state the old and new version at every changed stage. Confirm a
   nullable additive field uses the correct minor bump and every pinned writer,
   copy task, backfill, view, and publisher agrees. Treat rename, removal,
   incompatible type/nullability/order, or semantic changes as major-version work.
2. **Compatibility:** list affected writers and readers, coexistence or migration
   requirements, and any consumer that cannot read the proposed contract. A major
   change remains blocked until the developer confirms the migration strategy.
3. **Historical data:** decide `backfill required`, `regeneration required`,
   `future writes only`, or `unresolved`. A version bump never updates old
   partitions automatically.
4. **Execution order:** when historical work is required, list the exact dependency
   order: source/primary backfill, derived rerun, monthly regeneration, then DBX,
   Snowflake, and other publishers. Do not execute operational reruns unless the
   user explicitly authorizes them.
5. **Generated artifacts:** state which DBX or Snowflake files were regenerated,
   which generators ran, and whether the diff stayed inside the assigned dataset
   scope.
6. **Validation and release:** list completed static, generator, schema, and Alpha
   checks plus every remaining blocker. Only after this pass succeeds, prepare the
   ticket-specific commit message and PR description and hand staging, committing,
   dead-code checks, pushing, and draft-PR creation to `github:yeet`. Check only PR
   template items supported by evidence.
