# Relationship Awareness: upload-to-consumption research series

This series follows Relationship Awareness (RA) data from an uploaded archive to two distinct forms of consumption:

- the operational relationship view used by Pricing; and
- governed Primary RA datasets used by Data Studio and downstream analytics.

Each stage was researched independently against the local workspace checkouts. The reports emphasize why the boundary exists, the guarantees it provides, its failure modes, and the contract handed to the next stage.

## Workflow at a glance

```text
RAHaUT / service user
        |
        v
1. Upload and intake
   Authenticate, validate the ZIP envelope, persist session state,
   and atomically admit one active client run.
        |
        v
2. CQRS orchestration
   Correlate the request/run, gather the existing baseline,
   and coordinate asynchronous work through readiness gates.
        |
        v
3. Mapping and validation
   Convert client-shaped rows into typed RA imports, retain diagnostics,
   detect change, and resolve or reject duplicate identities.
        |
        v
4. RADAR transform and controlled publication
   Reconcile the new input with existing RA state, write DatabaseOutput,
   stage results, and publish relationship families to the active authority.
        |
        +------------------------------+
        |                              |
        v                              v
5. Primary RA extracts             6. Pricing UI
   Select one successful run,         Select relationships, load accounts,
   publish versioned datasets,        apply overrides and opportunity state,
   and fan out stable contracts.      and calculate relationship impact.
```

## Reports

1. [RA upload and Data Ingress intake](01-ra-upload-and-intake.md) — why admission, client isolation, and an explicit commit boundary matter.
2. [CQRS orchestration](02-cqrs-orchestration.md) — why a durable, event-driven coordinator is needed across asynchronous RA work.
3. [Mapping and validation](03-mapping-and-validation.md) — why client-specific source rows cannot safely enter the RA domain without typed mapping, diagnostics, and identity checks.
4. [Transform, load, and Relationship Service](04-transform-load-and-relationship-service.md) — why reconciliation and family-scoped publication protect operational consistency.
5. [Primary RA extracts](05-primary-ra-extracts.md) — why operational files become selected, versioned, date-partitioned analytical contracts.
6. [Pricing UI consumption](06-pricing-ui-consumption.md) — why displaying RA data and calculating pricing impact are separate, equally important paths.

## The central architectural insight

The flow is not a single application transaction. It crosses HTTP intake, blob and Data Lake state, CQRS commands/events, RADAR, application SQL staging, Relationship Service, Airflow, and Data Studio publication. Reliability comes from explicit boundaries: client/run identifiers, conditional admission, durable status, mapping-result artifacts, staging, relationship-family publication units, selected run metadata, and versioned dataset paths.

The two final branches also answer different questions:

- Pricing asks, **“What does this relationship mean for this banker, opportunity, and scenario now?”**
- Primary RA publication asks, **“What governed snapshot did this successful RA run produce for analytical consumers?”**

That distinction is the most useful guide when diagnosing a discrepancy. A correct Primary RA partition does not prove an already-open Pricing page is fresh, and a correct Pricing relationship does not prove that every primary extract task published its expected version and date partition.

## Important research findings

- Intake validates and admits the upload envelope; row/schema validity belongs to later stages.
- A completed validation phase may still contain record-level errors. Status alone is not proof that every source row survived.
- Legacy V2 handoff code remains, but its execution handler is unsupported. The current path is RADAR output followed by feature-flagged publication behavior.
- Relationship Service clients deliberately keep only a smaller Pricing-supporting footprint in application SQL; operational relationship/account reads are routed to Relationship Service.
- Primary ingestion selects one RA run before extracting individual tables, avoiding mixed snapshots across account and relationship datasets.
- Pricing has separate display and calculation flows. Opportunity state, scenarios, assumptions, payoffs, at-risk selections, and overrides can change calculated impact even when baseline relationship display is correct.

## Verification scope

This is static, read-only code research. No local test suites were run. No live client Airflow DAG, RA task execution, Operational ADLS artifact, Relationship Service deployment, or Data Studio partition was verified. The Primary RA report marks those operational availability questions explicitly.
