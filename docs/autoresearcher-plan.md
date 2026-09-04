# AutoResearcher plan

## Decision statement

Build an evidence-backed research factory that turns a bounded business question
into a ranked, reviewable experiment proposal.  It must not autonomously ship a
product decision.  Its job is to make the human decision-maker faster and better
informed by preserving source provenance, uncertainty, counter-evidence, and a
measurable path to value.

The first production slice is **feature-value investigation**: given a PL
Application feature, explain the client problem it addresses, trace its data
lineage to Snowflake, find adoption/outcome evidence, and recommend *test*,
*monitor*, or *do not pursue*.

## Operating principles

1. **Evidence before prose.** A claim has source, excerpt or query result,
   extraction time, owner, and confidence.  An unsourced claim is explicitly a
   hypothesis.
2. **One canonical semantic layer.** Entities, field definitions, transformations,
   metrics, and business rules are versioned; agents retrieve from it rather than
   reconstructing meaning from individual documents.
3. **Deterministic control plane; creative worker plane.** Input manifests,
   task routing, retrieval, scoring, budgets, tool permissions, and report schemas
   are deterministic.  Diverse models/personas only generate candidate
   explanations and hypotheses inside that bounded environment.
4. **Independent corroboration.** Separate researchers may not share drafts.
   A conclusion is promoted only when independent evidence supports it or a
   reviewer records why the sources are not truly independent.
5. **Falsifiability and abstention.** Every recommendation includes a proposed
   disconfirming observation.  Insufficient evidence is a valid, useful outcome.
6. **Humans hold decision rights.** Humans approve source access, labels,
   launch criteria, client contact, causal claims, and any action that affects a
   client or product roadmap.
7. **Cost and isolation are first-class.** Every run has time, token, query-cost,
   concurrency, and data-classification budgets; workers execute in isolated
   worktrees/sessions with read-only scoped credentials.

## Target architecture

```text
Question + success metric
        |
  Research brief compiler (deterministic)
        |
  Semantic retrieval: catalog + lineage graph + vector search
        |
  Parallel research cells (bounded, independent perspectives)
        |
  Evidence ledger + claim graph + contradiction detector
        |
  Peer-review panel + deterministic scorecard
        |
  Human gate -> experiment / monitor / reject / defer
        |
  Snowflake outcome tracking -> labels -> eval set -> improved routing
```

### Control plane

- `ResearchBrief`: question, decision owner, candidate population, time window,
  permitted sources, success metric, budget, required counterfactual, and exit
  criteria.
- `TaskManifest`: immutable run ID, model/prompt/tool versions, source snapshot
  IDs, seed, worker type, and budget.  This makes the harness replayable.
- `EvidenceLedger`: append-only records for artifacts, queries, claims, citations,
  reviewer annotations, scores, and human decisions.
- `ExperimentRegistry`: hypothesis, target cohort, metric definition, causal
  design, power/feasibility checks, outcome, and decision.

### Worker plane

Start with six narrow cells rather than a general swarm:

| Cell | Question it answers | Required evidence |
| --- | --- | --- |
| Client-results | What client pain and measurable outcome exist? | Support, adoption, retention, usage, interviews |
| Product-intent | Why was the feature built and for whom? | PRDs, tickets, release notes, roadmap decisions |
| Application semantics | What does the feature and each field mean? | Code, DTOs, schema definitions, tests |
| Pipeline lineage | How is the data ingested, transformed, and exposed? | DAGs, mappings, contracts, Snowflake catalog |
| Data-quality | Can the measurement be trusted? | Freshness, completeness, reconciliation, bias checks |
| Market | What alternative, demand signal, and differentiation exist? | Approved external sources and competitor evidence |

Persona variation belongs *within* a cell (for example, skeptical PM, client
operator, data steward), not as fictional evidence.  Persona outputs are
hypothesis generators and must cite the same ledger to affect a score.

### Semantic foundation

Use Snowflake as the system of record for raw evidence metadata, governed facts,
feature/adoption/outcome metrics, run telemetry, and training/evaluation labels.
Build Neo4j as a read-optimized relationship layer for multi-hop questions, not
as a second source of truth.  Maintain a stable ID and version for every object;
hydrate the graph deterministically from Snowflake and source repositories.

Core graph nodes: `Client`, `Feature`, `ClientProblem`, `UserRole`, `Metric`,
`Experiment`, `Outcome`, `ApplicationEntity`, `DTOField`, `Pipeline`, `DAG`,
`Dataset`, `SnowflakeTable`, `Transformation`, `Report`, `Claim`, `Evidence`,
`Decision`, and `Owner`.

Core relationships: `FEATURE_SOLVES`, `FEATURE_EMITS`, `FIELD_MAPS_TO`,
`PIPELINE_TRANSFORMS`, `DAG_PUBLISHES`, `TABLE_MEASURES`, `CLAIM_SUPPORTED_BY`,
`CLAIM_CONTRADICTS`, `EXPERIMENT_TESTS`, `OUTCOME_VALIDATES`, and `OWNER_STEWARDS`.

Retrieval is hybrid: deterministic graph traversal for lineage and governance,
vector retrieval for prose context, then a source-allowlisted answer generator.
Every answer returns the graph path and evidence IDs used.

## Research-to-decision workflow

1. **Frame:** decision owner writes a one-page brief and a measurable decision
   rule.  Example: "Should we invest in improving feature X for client segment Y?"
2. **Ground:** retrieve the semantic path from client problem -> application
   feature -> DTO -> pipeline -> Snowflake tables -> metric.
3. **Explore:** launch independent, budgeted cells.  Each produces claims,
   counterclaims, confidence, missing evidence, and references; no shared draft.
4. **Synthesize:** normalize claims, cluster duplicates, identify contradictions,
   and calculate evidence coverage and source independence.
5. **Verify:** peer panel checks semantic correctness, evidence quality,
   experimental soundness, and ROI.  It may only approve, reject, or request
   specific evidence; it cannot invent new facts.
6. **Decide:** a human marks the idea `test`, `monitor`, `reject`, or `defer`,
   explains the decision, and assigns an owner and review date.
7. **Learn:** ingest actual launch/adoption/revenue or saved-time outcomes;
   annotate proposal quality and feed only reviewed labels into future evals.

## Scoring and pruning

Do not select work by novelty or number of agents.  Rank the next investigation
by a transparent expected-value score:

```text
Priority = (expected client impact × probability of evidence-supported success
            × strategic fit × learning value)
           / (cost + time-to-answer + delivery risk)
```

Apply hard gates before ranking: named decision owner, permitted data, clear
metric, measurable cohort, lineage completeness, and a viable counterfactual.
Ideas failing a gate are retained as `defer` with the missing proof, rather than
silently disappearing.  Evidence strength, source independence, and data quality
cap the probability term.

ROI must distinguish correlation from causation.  Use randomized experiments
where feasible; otherwise pre-register a quasi-experimental design (matched
cohort, difference-in-differences, or interrupted time series), confounders,
minimum detectable effect, and stopping rule.  A sales claim requires a defined
link from exposure to qualified pipeline/conversion/retention and finance-approved
attribution; product usage alone is not proof of revenue.

## Harness and evaluation plan

### Reliability contract

The harness passes only if it can replay a run from its manifest, cite the
correct sources, abstain when evidence is insufficient, preserve access controls,
and produce the same deterministic score from the same ledger.  Model prose is
allowed to vary; the result schema, provenance, and gates are not.

### Toy evaluation suite (before live data)

Create synthetic fixtures with known ground truth and leakage-safe hidden labels:

1. **Lineage trace:** feature -> DTO -> DAG -> table; include a similarly named
   decoy field.  Grade exact path and citations.
2. **Semantic ambiguity:** the same label means different things in two domains.
   Grade correct disambiguation or abstention.
3. **Contradictory evidence:** a popular but stale report conflicts with current
   telemetry.  Grade time-awareness and explicit conflict handling.
4. **Causal trap:** adoption rises after a launch but a confounder explains it.
   Grade rejection of an unsupported revenue conclusion.
5. **Data-quality failure:** a metric has a late-arriving source and a broken
   cohort key.  Grade the decision to block or qualify the recommendation.
6. **Prompt injection/source safety:** untrusted text attempts to change tools or
   disclosure.  Grade refusal and preservation of source boundaries.
7. **Repeatability:** replay with frozen inputs and require invariant evidence
   IDs, score, decision gate, and budget compliance.

Score the suite with deterministic checks first (schema, citations, paths,
queries, budget) and calibrated human/LLM rubric judgments second.  Track
precision/recall of required claims, citation validity, abstention precision,
semantic-path accuracy, reviewer agreement, replay invariance, time-to-decision,
and cost per accepted insight.  Maintain a held-out set; never tune against it.

### Success thresholds for a pilot

- 100% of decision-driving claims have a resolvable evidence ID.
- 100% of harness runs reproduce control-plane outputs from the manifest.
- >=90% citation validity and >=85% semantic-lineage accuracy on the held-out
  synthetic suite before live pilot use.
- Human reviewers agree with the `test/monitor/reject/defer` recommendation on
  >=80% of adjudicated cases.
- At least one pilot recommendation produces a pre-registered, decision-useful
  measured outcome; absence of a positive sales effect is still useful if the
  system correctly recommends stopping investment.

## Delivery roadmap

### Phase 0 — Foundation (2 weeks)

- Define one decision domain and source access policy.
- Publish the ontology v0, research brief schema, evidence/report schema, and
  taxonomy (`fact`, `inference`, `hypothesis`, `decision`).
- Create synthetic fixtures and golden results; implement replay and budget tests.

### Phase 1 — Vertical slice (4 weeks)

- Ingest code metadata and a small approved Snowflake feature/usage data set.
- Materialize the first lineage graph and hybrid retrieval API.
- Implement the six worker contracts, evidence ledger, independent-run isolation,
  and an evidence-first report modeled on the existing RA workflow reports.
- Run 10 historical feature investigations with blinded human adjudication.

### Phase 2 — Verification and feedback (4 weeks)

- Add peer panel, contradiction detection, data-quality checks, ROI design
  templates, and human decision UI/workflow.
- Register the application/runs in Snowflake observability; track traces, scores,
  versions, and cost.
- Establish weekly label review and eval regression gates in CI.

### Phase 3 — Controlled scale (6 weeks)

- Expand approved sources (client feedback, support, market research, selected
  all-hands/product recordings subject to consent and retention policy).
- Add cross-model research cells only after the single-model harness passes the
  suite; compare quality, cost, and disagreement rather than assuming consensus.
- Launch prospective experiments and feed measured outcomes back into prioritization.

## Explicit dead ends to avoid

- A free-running swarm that can browse, query production, and write plans without
  an evidence ledger or decision owner.
- Treating simulated personas, model self-consistency, or panel consensus as
  ground truth.
- Vector-only retrieval for lineage, definitions, or governed metrics.
- A second manually maintained knowledge base that drifts from Snowflake/code.
- Optimizing reports for eloquence, number of citations, or thumbs-up counts
  instead of calibrated decision quality and measured outcomes.
- Allowing autonomous sales/product claims from observational telemetry.
- Premature multi-model orchestration: use a strong single path with regression
  evals first, then add parallelism only when it improves a tracked metric.

## Harness operations

Use tmux only as the operator console for isolated worker sessions; orchestration
must remain a durable queue/workflow with manifests, retries, timeouts, and
artifacts.  Herdr is relevant as a session/runtime layer for operating many agent
CLIs, but it does not replace the evidence ledger, semantic layer, or evaluation
control plane.  Codex/Claude/Cortex workers should share only the approved brief
and retrieved evidence pack, and their model/tool versions must be recorded.

## First pilot question

Select one existing PL Application feature with a known adoption event and a
traceable DTO-to-Snowflake path.  Produce a report that answers: what client
problem it serves; what the feature, fields, transformations, and metric mean;
whether adoption and outcome data are trustworthy; whether the observed outcome
supports a causal value claim; and the next smallest test or a documented reason
to stop.  The pilot is successful when a product/data leader can make a decision
from the report and later evaluate whether that decision was correct.
