# RA workflow report 04: transform/load and the Relationship Service boundary

## Why this stage matters

This is the point at which an RA run becomes usable operational data. It converts a run-scoped transformation result into either the legacy SQL RA model or the small set of Pricing-facing staging tables used by Relationship Service clients. Its most important job is **controlled publication**: a failed, incomplete, or superseded run must not quietly become the relationship/account picture that users price against.

The current code has three paths that coexist, and treating them as one path is a common source of confusion:

| Path | Current role | Operational data that `pl-application` publishes |
| --- | --- | --- |
| V2 transform | Retained handoff code only | None: its integration command handler throws `NotSupportedException`. |
| RADAR transform | Current supported external transform | ADLS `DatabaseOutput`, then SQL staging and family-by-family publication. |
| Relationship Service | Feature-flagged read model/archive service | `pl-application` stages relationship-list/UI support data; RA relationship/account truth is served through Relationship Service APIs. |

The decisive evidence is `IntegrationProcessManager`: every V2 execution entry point, including `QueueIntegrationRunForMappingResults`, says V2 runs are no longer supported and all RA clients must use RADAR (`pl-application/PrecisionLender.Application.CQRS.Core/ProcessManagers/Integration/IntegrationProcessManager.cs:164`, `:177`). Therefore a successful mapping-validation handoff to `StartV2TransformIfReady` is **not** a current production transformation route; it is an important legacy/compatibility seam to recognize while investigating older state or misconfiguration.

## Chronological flow

1. **Legacy V2 handoff is written, but cannot execute.** After mapping validation has an end time, `StartV2TransformIfReady` takes the *unvalidated* mapping-results blob URI, derives `IntegrationRequestId` and `IntegrationRunId` from the same client/request/run GUIDs, publishes `IntegrationRunForMappingResultsCreated`, sends `QueueIntegrationRunForMappingResults`, and marks `TransformAccountsStatus` started / `IsV2Run` true (`pl-application/PrecisionLender.Application.Core/Business/Direct/RA/RelationshipAwarenessBusinessService.cs:220`). The handler for the queue command throws (`pl-application/PrecisionLender.Application.CQRS.Core/ProcessManagers/Integration/IntegrationProcessManager.cs:177`).

   **Why important:** this detects an invalid client configuration early instead of silently using a stale implementation. An investigation of a V2-looking run should inspect configuration and command failure, rather than assume that a V2 transform loaded relationship data.

2. **RADAR gathers the current baseline before transforming.** The main Data Ingress process sends `RelationshipServiceGatherExistingData` while it begins `GatheringData` (`pl-application/PrecisionLender.Application.CQRS.Core/ProcessManagers/DataIngress/DataIngressProcessManager.cs:340`). The Relationship Service process manager calls `GatherExistingArchiveDataForRadarAsync`; that service sends client and PL run paths to Relationship Service (`pl-application/PrecisionLender.Application.CQRS.Core/ProcessManagers/RelationshipService/RelationshipServiceProcessManager.cs:48`, `pl-application/PrecisionLender.Application.Core/Business/Direct/RA/RelationshipServiceBusinessService.cs:74`). The application separately copies owners and, for non-Relationship-Service clients, existing database RA data into the run's lake area; it explicitly skips copying database relationship data when the feature flag is on (`pl-application/PrecisionLender.Application.Core/Business/Direct/RA/DataIngressBusinessService.cs:1578`).

   **Why important:** RA is a reconciliation, not merely an insert. The transform needs a consistent prior picture to decide which accounts/relationships persist, change, or close. Relationship Service gets that prior picture through its archive API; the legacy path gets it through the lake export.

3. **RADAR produces the run-scoped output; application code promotes it to staging.** `CopyRAResultsFromDataLakeToStagingTables` records `SavingToStagingTables` in both RA and RADAR status models and calls `CopyRadarRaResultsToDataBaseStaging` (`pl-application/PrecisionLender.Application.CQRS.Core/ProcessManagers/DataIngress/DataIngressProcessManager.cs:465`, `:501`). That service first deletes this run's prior staging result, then selects the legacy or Relationship-Service loader using the `Use Relationship Service` feature flag (`pl-application/PrecisionLender.Application.Core/Business/Direct/RA/DataIngressBusinessService.cs:858`).

   - The legacy loader bulk-loads relationship rows, loans, deposits, other accounts, collateral, participations, associations, overrides, custom details, closure records, and financial-statement artifacts from `DatabaseOutput` CSVs (`pl-application/PrecisionLender.Application.Core/Persistence/DataLake/DataIngressPersistence.cs:1635`).
   - The Relationship-Service loader intentionally copies only relationship list items, coverage-team members, delivery-to-promise aggregates, and relationship list items to close (`pl-application/PrecisionLender.Application.Core/Persistence/DataLake/DataIngressPersistence.cs:1715`).

   **Why important:** staging is the recoverable boundary between external transformation and user-visible data. It also makes the ownership split explicit: copying every legacy RA table for a Relationship Service client would create two competing sources of relationship/account truth.

4. **Queue publication by relationship family.** `QueueRelationshipFamiliesForSave` reads top-level parent IDs from `RelationshipsNewDB` on the legacy path, but from `RelationshipListItemsDB` for Relationship Service, and packages up to 512 parents per queue message (`pl-application/PrecisionLender.Application.Core/Business/Direct/RA/DataIngressBusinessService.cs:902`). `SaveRadarRaResultsToDatabase` selects the analogous feature-flagged publication path (`pl-application/PrecisionLender.Application.Core/Business/Direct/RA/DataIngressBusinessService.cs:932`).

   **Why important:** the top-level relationship family is the consistency unit. It avoids publishing one member of a household/family while another is still being processed, and bounds work/retry size for large clients.

5. **Publish the staged family and preserve Pricing links.** For Relationship Service clients, publication first retargets an opportunity that would point at a closing relationship; it deliberately leaves a relationship open if valid opportunities still reference it (`pl-application/PrecisionLender.Application.Core/Business/Direct/RA/DataIngressBusinessService.cs:945`, `:970`). It then drains the family queue and calls `FlipRaRelationshipFamilyForRelSrv`; non-Relationship-Service clients call the legacy family flip instead (`pl-application/PrecisionLender.Application.Core/Business/Direct/RA/DataIngressBusinessService.cs:1075`, `:1108`). The RelSrv flip is a `RelationshipListItemsDB` stored-procedure call scoped to client ID, run ID, and parent ID (`pl-application/PrecisionLender.Application.Core/Persistence/DataLake/DataIngressPersistence.cs:3247`).

   **Why important:** Pricing can continue to navigate a valid `RelationshipNewId` while the imported population changes. It also means a run can make partial family-level progress: errors are accumulated and reported, rather than treating the entire client dataset as one unbounded transaction.

6. **Mark terminal status only after the save attempt.** The save command records `SavingToDatabase` started/completed in both status systems, executes the selected save routine, and emits `DataIngressJobCompleted`; failures mark the stage/run failed and retry only IP-address-related SQL failures up to the configured retry limit (`pl-application/PrecisionLender.Application.CQRS.Core/ProcessManagers/DataIngress/DataIngressProcessManager.cs:728`, `:742`, `:748`). Later completion-history processing waits for RADAR's `RadarPostRun` activity because integrations output is expected there; it polls every five minutes and fails after four hours (`pl-application/PrecisionLender.Application.CQRS.Core/ProcessManagers/DataIngress/DataIngressProcessManager.cs:965`).

   **Why important:** “database save completed” does not by itself mean every downstream artifact exists. The explicit post-run gate prevents reporting an RA run as complete when its integrations output was not generated.

## The durable model and read boundary

### Legacy SQL RA model

For clients without `Use Relationship Service`, the full `DatabaseOutput` set is loaded to SQL staging and each top-level family is flipped into the application RA model. This includes durable relationships, core loan/deposit/other/treasury accounts, relationship-account associations, collateral/participations, and relationship/account overrides—the long list of staging copy calls begins at `DataIngressPersistence.cs:1635`. The actual publication is deliberately delegated to stored procedures through `RelationshipsNewDB.FlipRaRelationshipFamily` (`DataIngressPersistence.cs:3242`).

### Relationship Service model

For feature-flagged clients, the operational domain is owned by Relationship Service rather than recreated in `pl-application` SQL. The read adapter invokes service endpoints by `(clientId, relationshipNewId)`: relationship detail at `RelationshipServiceApiPersistence.cs:47`, summary at `:73`, core loan accounts at `:239`, account associations at `:291` and `:317`, totals at `:478`, and external-identifier lookup at `:727`. `RelationshipBusinessService` uses the configured relationship-service persistence to assemble relationship summaries for application callers (`pl-application/PrecisionLender.Application.Core/Business/Direct/RA/RelationshipBusinessService.cs:397`). The application-facing controller gets its summary through the domain access proxy (`pl-application/PrecisionLender.Application.Web/APIControllers/Application/RelationshipController.cs:67`).

**Why important:** the Pricing UI need not know whether data came from legacy SQL or Relationship Service. The boundary preserves the application relationship API while allowing Relationship Service to own account/association/override reads for enabled clients. The practical join key is the client-scoped `RelationshipNewId`; external identifiers are lookup keys, not substitutes for the application relationship GUID.

## Relationship Service archive operations

There are two distinct archive mechanisms:

1. **Run-time RADAR activation.** `RelationshipServiceActivateArchiveData` calls `ActivateArchiveForRadarAsync`, passing the client ID and run GUID as the archive version (`RelationshipServiceProcessManager.cs:62`, `RelationshipServiceBusinessService.cs:82`). In the current checkout, the only direct sender found is the *approved failed-validation/test run* path after it queues family publication (`DataIngressBusinessService.cs:1550`).
2. **Administrative remote archive import.** `RelationshipServiceImportBusinessService` creates a blob-backed job, asks Relationship Service to import a remote archive, polls its job status, then activates the archive and polls again (`RelationshipServiceImportBusinessService.cs:86`, `:134`, `:157`). The job is moved from active to history only after both import and activation timestamps exist (`:125`); failure/cancellation from Relationship Service throws with both application and service job IDs (`:177`).

**Ambiguity / verification target:** this checkout does not show normal successful RADAR runs sending `RelationshipServiceActivateArchiveData`; only the failed-validation approval path does. Do not infer normal activation timing from this repository alone. Confirm the RADAR service/pipeline contract and production command routing before diagnosing a “completed but inactive archive” incident.

## Transaction and failure boundaries

| Boundary | What it protects | Failure/recovery behavior |
| --- | --- | --- |
| RA run state / command dispatch | Do not queue V2 twice once transform has started | `TransformAccountsStatus.StartTime` guards V2 handoff; however, V2 execution is unsupported. |
| ADLS output to SQL staging | No direct partial write into live RA data | Existing staging for the same run is removed before copy (`DataIngressBusinessService.cs:868`); missing output files are simply not copied by individual loaders. |
| Top-level family flip | A family is the application publication unit | Queue work is acknowledged per message; concurrent workers can race on queue deletion and the code treats missing queue as another worker having completed it (`DataIngressBusinessService.cs:1075`). |
| Cross-system run status | Operators see RADAR and Data Ingress states | The manager updates both; a failed stage publishes `DataIngressJobFailed`. SQL IP-address failures are retried; other errors fail the run. |
| Archive import/activation | Do not mark an admin import complete before it is active | Polling persists job IDs/timestamps in blob storage and reschedules after one minute of work; a service failure throws. |

There is no evidence here of a single distributed transaction spanning ADLS, application SQL, RADAR, and Relationship Service. The design instead uses staging, family-scoped flips, idempotent-ish run IDs, status tracking, and retry/polling. That is an inference from the separate calls and durable queues above, not a claim about the internals of the external services.

## Identifiers and handoffs to watch

- `DataIngressRequestId` identifies the upload/request; `DataIngressRunId` identifies an attempt and carries the client identity. The same GUIDs are wrapped as `IntegrationRequestId`/`IntegrationRunId` for legacy V2 (`RelationshipAwarenessBusinessService.cs:237`).
- `RelationshipNewId` is client-scoped and is used for family flips, Relationship Service reads, opportunity linkage, and Pricing summaries.
- `ExternalIdentifier` is the source-facing lookup key; Relationship Service can resolve it to a relationship GUID (`RelationshipServiceApiPersistence.cs:727`).
- The transform-to-load handoff is RADAR `DatabaseOutput` in the run path → `CopyRAResultsFromDataLakeToStagingTables` → family queue → SQL flip/UI list items. The later operational-file handoff is RADAR post-run completion → integrations output; the application waits for it before completed-history handling (`DataIngressProcessManager.cs:965`).

## Guided reading path

1. `pl-application/PrecisionLender.Application.CQRS.Core/ProcessManagers/Integration/IntegrationProcessManager.cs:164` — establish why V2 is not the active route.
2. `pl-application/PrecisionLender.Application.Core/Business/Direct/RA/RelationshipAwarenessBusinessService.cs:220` — understand the legacy V2 handoff state that may still appear in run records.
3. `pl-application/PrecisionLender.Application.CQRS.Core/ProcessManagers/DataIngress/DataIngressProcessManager.cs:465` — follow RADAR output through staging and terminal status.
4. `pl-application/PrecisionLender.Application.Core/Persistence/DataLake/DataIngressPersistence.cs:1635` and `:1715` — compare legacy versus Relationship Service staging payloads.
5. `pl-application/PrecisionLender.Application.Core/Business/Direct/RA/DataIngressBusinessService.cs:932` and `:1075` — inspect feature-flagged family publication and opportunity protection.
6. `pl-application/PrecisionLender.Application.Core/Persistence/External/RelationshipServiceApiPersistence.cs:47` — trace the read contract used by Pricing/application services.
7. `pl-application/PrecisionLender.Application.Core/Business/Direct/RA/RelationshipServiceImportBusinessService.cs:86` — investigate archive imports separately from normal RA runs.

## Open questions

- **External transform implementation:** RADAR's transformation rules and the exact `DatabaseOutput` producer are outside `pl-application`; this report establishes its inputs/outputs and application-side loading only.
- **Normal archive activation:** as noted above, command emission for a normal completed RADAR run is not present in this checkout. Verify in RADAR orchestration/service code.
- **Primary RA extract timing:** the code proves that RADAR post-run is required for integrations output, but the exact storage path, schema, and DI primary consumer live outside this repository. Follow the post-run output in the RA/RADAR and `di-pipelines` repositories for the next report.
