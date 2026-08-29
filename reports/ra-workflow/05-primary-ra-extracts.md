# RA workflow report 05: operational output to Primary RA extracts

## Why this stage matters

This is the **publication boundary** between an operational RA run and governed analytical data.  The Pricing UI/Relationship Service produces run-scoped operational output; the RA primary pipeline turns selected `DatabaseOutput` CSVs into typed, versioned, date-partitioned Data Studio datasets.  That is what makes a completed RA run usable by data products without asking every consumer to understand an application run directory, file names, or RADAR's changed/unchanged-file convention.

The boundary is deliberately not a blind copy:

1. It selects one successful “best” run for a request date, preserving a consistent run identity across the many RA tables.
2. It enforces an explicit output header/schema and a dataset version before publishing historical partitions.
3. It makes the same primary result available in internal and client Data Marts, so derived jobs and client-facing Data Studio readers can use a stable contract.

**Scope/verification limit.** This report is static code research only. No client-specific DAG configuration, live Airflow task state, operational ADLS file, or Data Studio availability was verified. Statements about a particular client run existing, completing, or being readable are therefore unknown.

## The handoff in one view

`Relationship Service / RA operational run` → `OperationalADLS /ClientData/.../DataIngress/Request=.../RaRun=.../DatabaseOutput/*.csv` → `l3-main` status-selection and `ra_group` ingestion tasks → Historical Primary Data Studio partition → copies to Internal and Client Data Marts → high-quality/derived jobs, reports, and UI-facing data consumers.

The application boundary is important but indirect here: the pipeline does **not** call the Relationship Service API in the inspected task group. It reads the operational ADLS artifacts attributed to the selected RA run. The application/Relationship Service is consequently the producer-side authority; `ra_status` and the operational file contract are the pipeline-side availability boundary.

## 1. Select the run before reading any RA file

`get_ra_job_status` queries the PrecisionLender SQL Server and writes its result to Airflow XCom (`repositories/di-pipelines/dags/precisionlender/dags/task_groups/main/ra_jobs.py:135-182`). The status job transforms an application `RaRunPath` into `raLastBestDir`, timestamps, and `raVersion`; it selects the latest successful run of the latest request for each request date (`repositories/di-pipelines/de-jobs/src/datamart/jobs/ra/ra_status/get_ra_status.py:132-184`). The branch task sends a current result into `ra_group` and triggers separate manual backfill DAG runs for older valid results (`repositories/di-pipelines/dags/precisionlender/dags/task_groups/main/ra_jobs.py:53-77`, `80-123`).

This selection is important because account, relationship, and financial-statement extracts must describe the *same* RA run. Choosing a merely recent file independently per dataset would create mixed snapshots. The status job also detects duplicate result keys and warns when a run starts more than two days after its request date—an availability/freshness signal, since a delayed run may use materially different assumptions (`repositories/di-pipelines/de-jobs/src/datamart/jobs/ra/ra_status/get_ra_status.py:108-129`, `209-241`).

The RA task group obtains `raLastBestDir`, `raVersion`, and request date from that XCom; backfill runs receive the same values through `dag_run.conf` (`repositories/di-pipelines/dags/precisionlender/dags/task_groups/main/ra_jobs.py:187-200`). The client DAG itself is manually scheduled (`schedule=None`), so code alone does not prove when a client is triggered (`repositories/di-pipelines/dags/precisionlender/dags/l3_main_graph.py:186-205`). The backfill DAG is likewise manual (`repositories/di-pipelines/dags/precisionlender/dags/ra_backfill_graph.py:18-45`).

## 2. Resolve the operational file path and RADAR version

The task parameter contract is `raDirectory`, `raVersion`, and `raFile`. `OperationalRA` accepts only `RADAR` and constructs the operational path as:

```
/ClientData/Client={client_id}/DataIngress/Request={request_time}/RaRun={run_time}/{raFile}
```

(`repositories/di-pyjobs/di_pyjobs/path/relationship_awareness.py:11-44`, `136-154`). It parses both timestamps from the `raDirectory` in UTC and rejects an invalid directory rather than silently choosing a different location (`repositories/di-pyjobs/di_pyjobs/path/relationship_awareness.py:47-112`). The legacy helper separately asserts the run-directory type is `RaRun` and assigns it the RADAR version (`repositories/di-pyjobs/di_pyjobs/convention/path.py:38-77`).

This is important because it turns run metadata into a deterministic, client-isolated input path. It also makes the protocol strict: renamed directories, a non-RADAR `raVersion`, malformed timestamps, or a missing `DatabaseOutput` file stop an extract rather than publishing data from an arbitrary run.

For RADAR, a job using the change-detection base class reads both the named file and the sibling whose basename is prefixed with `Unchanged`, appending the two result sets. It logs an empty-data condition only if both are empty (`repositories/di-pyjobs/di_pyjobs/job/standard/batch.py:214-327`). This matters because reading only the changed CSV would produce an incomplete snapshot whenever Pricing/RA leaves unaffected records in the `Unchanged...` artifact.

## 3. Representative exact extract: commercial loan accounts

| Contract element | Static configuration |
| --- | --- |
| Airflow task symbol | `get_core_commercial_loan_accounts` |
| Pipeline job | `datamart.jobs.ra.core_commercial_loan_accounts.to_datamart.GetCoreCommercialLoanAccounts`, or Spark `CoreCommercialLoanAccountsIngestion` when the client/backfill resource override is present |
| Operational input | `OperationalADLS` + `di_pyjobs.path.relationship_awareness.OperationalRA` |
| `raFile` | `DatabaseOutput/dbStagingCoreCommercialLoanAccounts.csv` |
| Run metadata | `raDirectory=raLastBestDir`; `raVersion` from status XCom (or backfill conf); `windowStart=dfFormatRequestDate` |
| Historical output | `HistoricalDataMartADLS` + `DataStudioHistorical`, dataset `PL_RelationshipAwareness/Core/CoreCommercialLoanAccounts`, stage `Primary`, version `v2.2` |
| Publication copies | `core_commercial_loan_accounts_to_internal_adls` to `InternalDataMartADLS`/`DataStudioInternal`; `core_commercial_loan_accounts_to_client_datamart_adls` to `ClientDataMartADLS`/`DataStudioClient` |

The authoritative task definition is `repositories/di-pipelines/dags/precisionlender/dags/task_groups/main/ra_jobs.py:516-620`. Both publication copies are direct downstream tasks (`repositories/di-pipelines/dags/precisionlender/dags/task_groups/main/ra_jobs.py:1416`). The batch job explicitly types its operational input and defines the output header (`repositories/di-pipelines/de-jobs/src/datamart/jobs/ra/core_commercial_loan_accounts/to_datamart.py:3-181`, `184-195`). For clients routed to Spark, the alternate runner reads the main and `Unchanged` CSVs, enforces metadata schema, repartitions, and writes CSV output (`repositories/di-pipelines/ds-jobs/src/datascience_jobs/jobs/primary_ingestion/ra/core_commercial_loan_accounts.py:10-43`).

That representative task shows the three concerns held together by the primary boundary: source lineage (`raDirectory` and `raFile`), semantic compatibility (typed/header-controlled version `v2.2`), and availability (historical result followed by two independent publication destinations).

## 4. Dataset families published by the RA group

The code defines a broad RA primary surface; this is a family map, not an exhaustive table inventory.

| Family | Representative operational artifact | Primary dataset family | Why it matters |
| --- | --- | --- | --- |
| Core accounts | `dbStagingCoreCommercialLoanAccounts.csv`, plus deposit, consumer, other, treasury, amortization, and account-financial-statement outputs | `PL_RelationshipAwareness/Core/*` | Preserves account-level balances, pricing, product, and financial facts for analytics and later account/relationship derivations. |
| Relationships | `dbStagingRelationshipNew.csv` | `PL_RelationshipAwareness/Relationships/Relationships` | Provides the relationship identity and ownership grain that joins accounts into a customer/portfolio view. |
| Relationship calculations | relationship financial statements, aggregate balances, coverage-team, and supplemental-data outputs | `PL_RelationshipAwareness/Relationships/*` | Carries relationship-level pricing/economic outcomes and organizational ownership needed to interpret the account facts. |
| Assumptions and financial-statement breakdowns | RA assumptions, account/loan/deposit/other/treasury and expense breakdown output files | Core/Assumptions and Core financial-statement datasets | Preserves the calculation context and component facts behind Pricing/RA results. |

The relationships task has the same operational-to-historical shape: it reads `DatabaseOutput/dbStagingRelationshipNew.csv`, publishes `PL_RelationshipAwareness/Relationships/Relationships` version `v1.2`, and then copies that historical partition to internal and client resources (`repositories/di-pipelines/dags/precisionlender/dags/task_groups/main/ra_jobs.py:2157-2262`). The explicit dependency fan-out for relationships, coverage teams, financial statements, and aggregate balances is visible at `repositories/di-pipelines/dags/precisionlender/dags/task_groups/main/ra_jobs.py:3165-3180`.

## 5. Primary Data Studio contract and paths

Primary metadata is a second, code-owned contract—not merely documentation. For commercial loans it declares `Primary / PL_RelationshipAwareness / Core / CoreCommercialLoanAccounts`, latest `v2.2`, IDs `Id` and `RaRunId`, and a schema beginning with RA run and account identity fields (`repositories/di-pipelines/ds-jobs/src/datascience_jobs/meta_data/datasets/primary/pl_relationship_awareness/core.py:283-340`). Relationships similarly declares `Primary / PL_RelationshipAwareness / Relationships / Relationships`, latest `v1.2`, with `ExternalIdentifier` and `RaRunId` as identifiers (`repositories/di-pipelines/ds-jobs/src/datascience_jobs/meta_data/datasets/primary/pl_relationship_awareness/relationships.py:12-82`).

`DataStudioHistorical` writes the canonical historical partition at:

```
/ClientId={client_id}/L3/v1.0/Primary/PL_RelationshipAwareness/{group}/{dataset}/
  InstancePartition={client_id}/VersionPartition={datasetVersion}/DatePartition={YYYYMMDD}/
```

(`repositories/di-pyjobs/di_pyjobs/path/data_studio.py:95-137`). Internal copies add an `InstanceGroupPartition` under the `datamart` filesystem (`repositories/di-pyjobs/di_pyjobs/path/data_studio.py:276-349`); client copies use the client Data Mart `datamart` path with the same version/date partitioning but no group partition (`repositories/di-pyjobs/di_pyjobs/path/data_studio.py:454-490`).

This versioned/date-partitioned layout is important for reproducibility: a downstream reader can select both a particular schema version and an RA request-date snapshot. Conversely, a field addition must be treated as a contract change: update the producer’s header/schema and consumers’ requested version together. **Inference:** the DAG task’s version and the metadata class are intended to agree; the commercial-loan example does (`v2.2`). I did not verify every RA task’s version against every metadata class.

## 6. Availability, failures, and observability

The operational prerequisites are: a selected successful run in the application status source, a parseable RADAR directory/version, and one or both changed/unchanged CSV artifacts. `ra_status` emits the selected/current/backfill metadata to logs/XCom and logs delayed-run and backfill warnings (`repositories/di-pipelines/de-jobs/src/datamart/jobs/ra/ra_status/get_ra_status.py:225-257`). Ingestion and copy tasks declare two retries, a retry delay, and timeouts; representative ingest timeout is one hour while copies use the standard copy timeout (`repositories/di-pipelines/dags/precisionlender/dags/task_groups/main/ra_jobs.py:538-570`, `574-620`).

Main failure modes and why they are safe-to-investigate rather than silent:

- **No eligible RA run:** the branch has no `current` entry and does not start the transform group (`repositories/di-pipelines/dags/precisionlender/dags/task_groups/main/ra_jobs.py:65-77`). This is a skip/availability condition, not evidence that an output should be fabricated.
- **Late or ambiguous run:** warnings/validation in `RaStatus` reveal stale execution or duplicate selection keys before file movement (`repositories/di-pipelines/de-jobs/src/datamart/jobs/ra/ra_status/get_ra_status.py:115-129`, `209-241`).
- **Bad path/version or absent artifacts:** `OperationalRA` rejects invalid version/directory syntax; the extract cannot resolve the intended file (`repositories/di-pyjobs/di_pyjobs/path/relationship_awareness.py:32-44`, `59-74`).
- **Empty changed and unchanged files:** the change-detection runner logs empty output and exits rather than publishing an invented snapshot (`repositories/di-pyjobs/di_pyjobs/job/standard/batch.py:308-318`).
- **Schema drift:** the batch path constrains input dtypes and output headers, while the Spark path sources its schema from metadata; both make an unexpected producer contract visible at ingestion rather than letting inferred types leak downstream (`repositories/di-pipelines/de-jobs/src/datamart/jobs/ra/core_commercial_loan_accounts/to_datamart.py:3-181`, `repositories/di-pipelines/ds-jobs/src/datascience_jobs/jobs/primary_ingestion/ra/core_commercial_loan_accounts.py:30-43`).
- **Partial publication:** historical is the source for two separately retried copies. A historical success does not by itself prove both internal and client destinations are present; inspect the corresponding Airflow tasks.

The main DAG deliberately provides `ra_transform_no_failure` so downstream work can run even when RA transforms are skipped (`repositories/di-pipelines/dags/precisionlender/dags/l3_main_graph.py:425-454`). This is an availability caveat for consumers: a downstream task’s success can mean “worked with existing/independent inputs,” not necessarily “a new RA primary partition was published today.”

## 7. Representative downstream handoff

The direct next step is not generally the Pricing UI—it is Data Studio publication and derived/data-product work. The main graph makes RA validation depend on `ra_transforms`, and relationship-feature/descendant workloads depend on that validation output (`repositories/di-pipelines/dags/precisionlender/dags/l3_main_graph.py:505-517`). Representative consumers explicitly request primary Relationships or Core Commercial Loan Accounts metadata, including relationship descendants, relationship features, similar-loans portfolio data, owner-match audit reporting, and credit-migration reporting (`repositories/di-pipelines/ds-jobs/src/datascience_jobs/jobs/data/relationship/relationship_descendants.py:9-18`, `repositories/di-pipelines/ds-jobs/src/datascience_jobs/jobs/data/relationship/relationship_features_client_specific.py:3-20`, `repositories/di-pipelines/ds-jobs/src/datascience_jobs/jobs/modeling/similar_loans/similar_loans_portfolio_data.py:10-32`).

For a field/data incident, hand off with this minimum evidence: client ID; `raLastBestDir`, `raVersion`, and request date selected by `RaStatus`; exact `raFile`; ingest task ID and status; dataset/version/date partition; and both copy-task statuses. Then decide whether the fault predates the boundary (Pricing/Relationship Service produced missing/wrong operational CSV), is at the boundary (path/schema/merge/publication failure), or is downstream (consumer selecting a different version/date or applying a derived transformation).

