---
name: pl-dipl
description: Validate PrecisionLender Data Intelligence Pipeline changes before exposing them to the team. Use for pull requests, code requests, and changes involving datasets, DAGs, schemas, resources, or production-facing behavior.
---

# PL-DIPL peer review

## Review-only boundary

This skill is purely a code-review tool. Do not edit source code, tests, configuration, tickets, pull requests, or other project artifacts while using it. Report findings, risks, missing validation, and recommended follow-up work to the user instead.

## Local Test-Suite Policy

When working in `di-pipelines`, `di-scheduling`, or `di-pyjobs`, do not run local unit, integration, or full test suites. Use static inspection, targeted non-test checks, and remote or Alpha evidence instead. Run a local test suite only when the user explicitly requests it.

Before sharing a code request with the team, check every applicable item below. Mark an item complete only after inspecting the diff or attaching evidence. Keep unresolved questions visible in the PR description.

## Ticket and scope alignment

- [ ] Read the Jira ticket or source requirement closely and identify its requested behavior, affected data/contracts, acceptance criteria, and explicit exclusions.
- [ ] Compare every changed file and material diff hunk to those ticket requirements. Confirm the implementation delivers the requested changes.
- [ ] Identify and call out code, configuration, schema, metadata, tests, or cleanup that is extraneous to the ticket goal.
- [ ] Inspect deleted code separately. Confirm each deletion is required by the requested change or is necessary to preserve correctness; flag deletions that are unrelated or insufficiently justified.

## Code quality

- [ ] Names, casing, imports, formatting, lint, and pre-commit checks are clean.
- [ ] No unused code, debug values, temporary comments, stale files, or obsolete schema paths remain.
- [ ] No useless or duplicate wrapper functions remain. Flag helpers that only forward a call or contain fewer than about three lines of logic when the call should be inlined instead.
- [ ] Shared helpers and typed override/configuration classes are used consistently instead of ad-hoc dictionaries.
- [ ] Version changes are intentional and additive fields are placed according to repository compatibility rules.

## Data and pipeline behavior

- [ ] The job's compute mode and resource allocation are correct for its workload.
- [ ] Paths use the repository's standard path/context helpers.
- [ ] Date/window/rundate behavior and scheduling timing account for source-data availability.
- [ ] Nullability, field types, casing, projections, and empty-input behavior match the source contract.
- [ ] Dataset versions, downstream copies, Databricks/Snowflake schemas, secure views, and metadata are updated together when applicable.
- [ ] Runtime-parsed clients, tenant-specific resources, and feature/client allowlists are handled explicitly.

## Evidence

- [ ] Focused test coverage exists for changed logic and edge cases, when applicable.
- [ ] Static checks, lint, type checks, and user-authorized test evidence are recorded.
- [ ] Alpha/integration validation proves the DAG parses and affected jobs complete.
- [ ] Output data is checked for expected rows, fields, versions, non-null values, and downstream compatibility.
- [ ] Resource-sensitive changes are validated for representative clients, including relevant override/no-override cases.
- [ ] Operational follow-up is documented: scheduling, backfill/rerun steps, dependent deployments, and monitoring.

## Review readiness

- [ ] The PR description contains commands, logs, links, or screenshots for the validation above.
- [ ] Reviewer questions are answered or explicitly called out as remaining decisions.
- [ ] OpenSpec or equivalent planning artifacts are archived.
- [ ] The PR is ready for the requested reviewers and the team communication channel is notified.
