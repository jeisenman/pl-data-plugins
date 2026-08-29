# RA workflow report 02: Data Ingress and CQRS orchestration

## Purpose and boundary

This report covers the coordination layer after an RA upload has been committed and before mapped data is handed to the subsequent transformation path. It is not the file-extraction implementation, the mapping algorithm in detail, or the eventual primary extract. Its purpose is to explain why the orchestration exists: it makes a multi-stage, failure-prone import observable, ordered, and restartable without assuming that command delivery is synchronous or exactly-once.

There are two related flows in the current code:

1. **Radar / Data Ingress flow.** `DataIngressProcessManager` accepts `DataIngressFileCommitted`, verifies client eligibility, extracts the upload, registers watchdog state, gathers existing Relationship Service archive data, and (when configured) creates the CQRS RA run. See `repositories/pl-application/PrecisionLender.Application.CQRS.Core/ProcessManagers/DataIngress/DataIngressProcessManager.cs:163-200`, `:236-266`, and `:323-465`.
2. **RA run / mapping flow.** `RADataProcessManager` creates persistent run state and coordinates existing-owner collection, mapping, mapping validation, and a transform handoff. See `repositories/pl-application/PrecisionLender.Application.CQRS.Core/ProcessManagers/DataIngress/RADataProcessManager.cs:21-32` and `:59-335`.

The names "V2" and "V3" in this code are historical compatibility terminology, not proof of the currently deployed production path. In particular, the V2 queue handler now throws `NotSupportedException` because all RA clients are expected to use Radar (`repositories/pl-application/PrecisionLender.Application.CQRS.Core/ProcessManagers/Integration/IntegrationProcessManager.cs:172-180`). Treat the V2-transform handoff described below as a code-level compatibility seam that needs runtime/configuration confirmation before relying on it operationally.

### Evidence-path convention

All line citations in this report were verified against the workspace checkout under `repositories/pl-application` (not a sibling clone). To keep later citations readable, these unambiguous aliases denote the following repository-relative files:

- **DI PM** — `repositories/pl-application/PrecisionLender.Application.CQRS.Core/ProcessManagers/DataIngress/DataIngressProcessManager.cs`
- **RA PM** — `repositories/pl-application/PrecisionLender.Application.CQRS.Core/ProcessManagers/DataIngress/RADataProcessManager.cs`
- **RA business service** — `repositories/pl-application/PrecisionLender.Application.Core/Business/Direct/RA/RelationshipAwarenessBusinessService.cs`
- **Relationship Service PM** — `repositories/pl-application/PrecisionLender.Application.CQRS.Core/ProcessManagers/RelationshipService/RelationshipServiceProcessManager.cs`
- **Integration PM** — `repositories/pl-application/PrecisionLender.Application.CQRS.Core/ProcessManagers/Integration/IntegrationProcessManager.cs`
- **Data Ingress admin API** — `repositories/pl-application/PrecisionLender.Application.Web/Areas/Admin/Controllers/DataIngress/Api/DataIngressApiController.cs`

## Chronological flow

| Order | Command/event and responsible code | What it coordinates | Why it matters |
|---|---|---|---|
| 1 | `DataIngressFileCommitted` -> `DataIngressUploadRAFiles` | Checks `EnableCoreIntegration` and Radar configuration, creates the older RA-run record, then queues upload handling. | Prevents an unsupported client from creating a partial pipeline state. The explicit command boundary keeps the commit handler short and lets failures be recorded against the request/run. **DI PM:163-200** |
| 2 | `DataIngressUploadRAFiles` | Marks file extraction started/completed, invokes `StartRelationshipAwarenessRun`, adds the run to the watchdog, sends `DataIngressGatherExistingData`, and publishes `DataIngressRaRunStarted`. | The watchdog is armed *before* database gathering, which gives operators a recovery signal for a hung external/long-running stage. Uploaded file names are only read after the extraction call, preserving the intake contract. **DI PM:236-266** |
| 3 | `DataIngressGatherExistingData` -> `RelationshipServiceGatherExistingData` | Starts a watchdog stage; updates Data Ingress and Radar statuses; commands Relationship Service to gather archive data; moves existing data to Data Lake; then publishes `DataIngressGatherExistingDataCompleted`. | Mapping/import must be reconciled with the client’s current relationship archive, not only the newly uploaded files. This isolates the Relationship Service call behind a CQRS command while keeping Data Lake paths as the completion contract. **DI PM:323-368; Relationship Service PM:48-60** |
| 4 | `DataIngressGatherExistingDataCompleted` -> `DataIngressUploadV2Fileset` -> `CreateDataIngressRARun` | For `ShouldRunV2Transform`, removes the currently-running blob, reloads the saved file set, then creates the new RA CQRS run with `IntegrationRunOptions`. | This is the bridge from file intake/data-lake setup to durable RA run-state orchestration. Removing the blob is explicitly intended to avoid interference from multiple queued V2 uploads. **DI PM:403-465** |
| 5 | `CreateDataIngressRARun` -> `RunRACreateExistingClientData` | Creates the RA run state transactionally, emits `DataIngressRaRunStarted`, publishes the transform-started compatibility event, then queues owner gathering. | A stable `DataIngressRequestId` + `DataIngressRunId` correlates all later commands/events. Persisting state before sending work establishes a recovery point. **RA PM:59-83; RA business service:74-85** |
| 6 | `RunRACreateExistingClientData` -> `RunRACreateExistingClientOwnerData` | Emits a started event and asks the business service to pass the readiness gate. The service marks "Get Existing Data" started and transactionally queues owner collection. | Owner data is a mapping dependency: server-side mapping uses saved client owners. The gate avoids double-starting the downstream command. **RA PM:88-115; RA business service:89-105** |
| 7 | `RunRACreateExistingClientOwnerDataStopped` -> `RunRACreateMappingResults` | On completed owner gathering, starts mapping if ready and separately completes the encompassing existing-data status. | It permits mapping to start as soon as its direct prerequisite is complete, while still retaining a clear aggregate status for the run. **RA PM:154-175; RA business service:168-191** |
| 8 | `RunRACreateMappingResults` -> `RunRACreateMappingStopped` | Creates an integration mapping ID, emits start/stop events, builds and indexes mapping results, records join/mapping errors, and persists completion. | The mapping-result ID is the durable handoff artifact: it permits validation and later transform stages to refer to an immutable run-specific result rather than re-reading intake files. **RA PM:205-269; RA business service:492-597** |
| 9 | `RunRAValidateMappingResults` -> transform handoff | Validation uses the configured duplicate strategy, creates a separate validated result, and only then permits `StartV2TransformIfReady`. | This separates syntactic mapping from duplicate/relationship correctness and preserves validation failures as structured run errors. **RA PM:272-335; RA business service:623-696** |

## Run state and readiness gates

`RelationshipAwarenessBusinessService` owns the state transitions; the process manager should be read as an event router, not the authoritative state machine. `CreateRun` persists run state and adds `DataIngressRaRunStarted` to the transaction (**RA business service:74-84**). Every action then follows the same pattern: atomically update `RARunStateDTO`, set a part status, and add the next command/event to `CurrentTransaction`.

The critical gates are:

- Existing data: do nothing if owner gathering already has a start time; otherwise mark `ExistingDataStatus` started and add `RunRACreateExistingClientOwnerData` (**RA business service:89-105**).
- Mapping: only add `RunRACreateMappingResults` when owners are `Completed`, and only if `MappingStatus.StartTime` is absent (**RA business service:168-191**).
- Validation: only add `RunRAValidateMappingResults` when mapping is completed and validation has not started (**RA business service:194-217**).
- Transform: only hand off after validation has an end time and no transform start time exists (**RA business service:220-263**).

These gates matter because completion events can be retried or delivered more than once. The state update makes a duplicate event harmless at the scheduling boundary. Once work has begun, the worker methods defend against concurrent re-execution: owner gathering, mapping, and validation permit only `null`, `NotStarted`, or `Started` states; otherwise they throw `DataIngressMultiRunException` (**RA business service:51, 360-406, 499-519, 629-649**). This is evidence of *at-least-once-aware* behavior, not evidence of end-to-end exactly-once delivery.

## Async and handoff contracts

Commands and events cross process-manager boundaries through `ICommandSender` and `IEventPublisher`; the code makes no synchronous return-value dependency between stages. In fact, calls that are internally asynchronous at the Relationship Service boundary are waited inside that handler (`GatherExistingArchiveDataAsync(...).GetAwaiter().GetResult()`), after the original Data Ingress manager already sent the command (**Relationship Service PM:48-60**).

The concrete handoffs are:

- **Intake to gather:** `requestId`/`runId`, watchdog state, and the extracted/uploaded file set. Data Lake run paths (`plRunPath`, `clientRunPath`) are published only after existing data is moved (**DI PM:345-367**).
- **Gather to mapping:** saved owners plus client XML join/mapping configuration and the uploaded file set. Mapping loads all three before calling `PerformJoins` and `ProcessMappings` (**RA business service:524-559**).
- **Mapping to validation:** `IntegrationMappingResultId`; an indexed result and search index are created before the completed event is added (**RA business service:561-597**).
- **Validation to transformation:** the run state’s mapping-result ID is converted to a blob URI, then an integration-created event and queue command carry that URI and run options (**RA business service:237-260**). **Inference:** this URI is designed as a decoupled payload contract between the mapping and transform systems. The production consumer of this compatibility handoff is uncertain because the queue handler is now explicitly unsupported.

## Failure, retry, and watchdog behavior

The legacy intake/gather portion has bounded retry: both upload and gather reschedule themselves through `ScheduleCommand` with an exponential sequence based on 3, up to the configured maximum of three retries (**DI PM:69-70, 291-319, 370-400**). Before a gather retry, the watchdog stage is stopped; terminal failure updates Radar/Data Ingress status and publishes `DataIngressJobFailed` (**DI PM:376-399**). A cancellation after Data Lake movement produces `DataIngressJobCancelled` instead of a successful completion (**DI PM:350-368**).

The RA-run portion distinguishes duplicate/concurrent work from ordinary failures. `DataIngressMultiRunException` is recorded with exception details but intentionally does not emit a stopped event, because the original instance may still be running; ordinary exceptions publish a fatal stopped event with typed error details (**RA PM:118-151, 205-239, 272-306**). Stop handlers persist errors/exceptions before either scheduling the next stage or asking the run service to complete the run (**RA PM:242-269, 309-335**).

For operator visibility and repair, the admin API exposes watchdog state (current stage, last update, suspected-stalled timestamp, worker information), lets an admin force a run to `FailedStalled`, and exposes a restart from Load DB Staging operation (**Data Ingress admin API:46-73, 96-124, 149-177**). That recovery endpoint is for the older Radar staging flow, not shown as a restart mechanism for the mapping gates in this report.

## Key code map

- `repositories/pl-application/PrecisionLender.Application.CQRS.Core/ProcessManagers/DataIngress/DataIngressProcessManager.cs:163` — committed-file entry point, legacy intake, retries, watchdog, and bridge to the CQRS RA run.
- `repositories/pl-application/PrecisionLender.Application.CQRS.Core/ProcessManagers/DataIngress/RADataProcessManager.cs:21` — command/event coordinator for the RA run-state workflow.
- `repositories/pl-application/PrecisionLender.Application.Core/Business/Direct/RA/RelationshipAwarenessBusinessService.cs:74` — durable state transitions, readiness gates, owner gathering, mapping, validation, and transform handoff.
- `repositories/pl-application/PrecisionLender.Application.CQRS.Core/ProcessManagers/RelationshipService/RelationshipServiceProcessManager.cs:48` — Relationship Service archive-gather command boundary.
- `repositories/pl-application/PrecisionLender.Application.Web/Areas/Admin/Controllers/DataIngress/Api/DataIngressApiController.cs:46` — operational watchdog and stalled-run interface.
- `repositories/pl-application/PrecisionLender.Application.CQRS.Core/ProcessManagers/Integration/IntegrationProcessManager.cs:177` — evidence that the retained V2 transform queue command is no longer supported.

## Guided reading path

1. Read **DI PM:163-320** to understand eligibility checks, extraction, retry semantics, and watchdog registration.
2. Read **DI PM:323-465** alongside **Relationship Service PM:48-60** to see why existing archive data is gathered before creating the new RA CQRS run.
3. Read **RA PM:59-199**, then **RA business service:74-191**. Pair each event handler with the corresponding state-gate method; this reveals the real ordering guarantee.
4. Read **RA PM:205-335** with **RA business service:492-696** to follow mapping, persisted errors, duplicate resolution, and validation.
5. Finally read **RA business service:220-263** and **Integration PM:172-180**. This is the current architectural question to resolve before changing this boundary: whether any live configuration reaches the now-unsupported V2 queue, or whether Radar supersedes that branch entirely.
