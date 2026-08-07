---
name: dto-contract-gap-analysis
description: Compare week-to-week DTO or API contract changes in pl-application with fields represented in di-pipelines. Use when identifying newly added contract fields, assessing whether data ingestion already supports them, producing a field-gap report, or deciding whether a new field is useful to track historically.
---

# DTO Contract Gap Analysis

Use this skill to turn an application-contract diff into a reviewable data-history backlog. A field absent from `di-pipelines` is evidence to investigate, not proof that ingestion is missing: it may be renamed, derived, or intentionally excluded.

## Workflow

1. Resolve the two Git refs. Default to the current `HEAD` and its first-parent commit at least seven days earlier; state the actual refs and dates in the report. Prefer explicit `--from-ref` and `--to-ref` when a release boundary is known.
2. Limit the source scan to DTO/contract paths or an explicit `--contract-glob`. Do not report ordinary persistence entities or view models as API-contract changes unless the requester includes them.
3. Run the bundled scanner. It extracts likely added field declarations from Java, C#, TypeScript, and Kotlin diff lines, then searches `di-pipelines` by normalized field-name tokens.
4. Inspect every candidate manually before recommending work. Check source semantics, containing DTO, naming variants, mapper/schema definitions, and existing derived equivalents.
5. Present the decision question verbatim for each unresolved candidate: **Would this field be useful to track over time?** Explain the recommendation in one or two evidence-based sentences.

## Run the scanner

```bash
python3 scripts/scan_contract_gaps.py \
  --application /path/to/pl-application \
  --pipelines /path/to/di-pipelines \
  --from-ref 'main@{7 days ago}' \
  --to-ref main \
  --contract-glob '*Dto*.cs' \
  --output contract-gap-report.md
```

Use one or more `--contract-glob` arguments. The default globs favor names containing `Dto`, `DTO`, `Contract`, `Request`, or `Response`; adjust them to the repository's actual public-contract convention. Use `--json-output` when an automated job will consume the results.

## Interpret results

- **represented**: an exact or plausible normalized-name match appears in `di-pipelines`. Verify lineage; a text match alone is insufficient.
- **candidate gap**: no match was found. Determine whether the field has a renamed equivalent, is derived only, or needs source-to-history work.
- **not historical**: exclude only with a stated reason, such as presentation-only state, an ephemeral command parameter, or an existing durable equivalent.

Rank historical value using: event/change semantics, business decisions or reporting it enables, likely future questions, value of point-in-time history, stability/meaning of the field, privacy classification, and expected ingestion cost. Do not recommend tracking sensitive values without confirming governance and access requirements.

## Report format

Start with source/pipeline refs, scan scope, and limitations. Then use one row per new field:

| DTO and field | Type/nullability | Pipeline evidence | Historical-value analysis | Decision |
|---|---|---|---|---|
| `OpportunityDto.riskRatingEffectiveDate` | `DateTime?` | No mapping found | Captures when a risk posture took effect, enabling transition timing analysis. **Would this field be useful to track over time? Yes.** | Investigate ingestion |

Follow the table with false-positive notes and a short list of concrete next actions. Never treat the scanner output as a contract compatibility assessment or a complete schema diff.

## Completion notification

When the requester asks for a Slack notification, send a direct Slack message after the report is complete. Include the compared refs, number of unique fields, number represented, number of candidate gaps, and the report location if one was created. Resolve the requester to a real Slack user ID before sending; never infer one from an email address.
