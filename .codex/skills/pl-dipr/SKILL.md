---
name: pl-dipl
description: Validate PrecisionLender Data Intelligence Pipeline changes before exposing them to the team. Use for pull requests, code requests, and changes involving datasets, DAGs, schemas, resources, or production-facing behavior.
---

# PL-DIPL peer review

Before sharing a code request with the team, check every applicable item below. Mark an item complete only after inspecting the diff or attaching evidence. Keep unresolved questions visible in the PR description.

## Request validity

- [ ] The request links to the ticket or source requirement. Check Jira ticket. Validate no extraneous code exists.
- [ ] Check Jira ticket. Validate no extraneous code exists. The implementation matches the request; unrelated cleanup and scope creep are removed.

## Code quality

- [ ] Names, casing, imports, formatting, lint, and pre-commit checks are clean.
- [ ] No unused code, debug values, temporary comments, stale files, or obsolete schema paths remain.
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

- [ ] Focused unit tests cover changed logic and edge cases.
- [ ] Lint, type checks, and relevant test suites pass.
- [ ] Alpha/integration validation proves the DAG parses and affected jobs complete.
- [ ] Output data is checked for expected rows, fields, versions, non-null values, and downstream compatibility.
- [ ] Resource-sensitive changes are validated for representative clients, including relevant override/no-override cases.
- [ ] Operational follow-up is documented: scheduling, backfill/rerun steps, dependent deployments, and monitoring.

## Review readiness

- [ ] The PR description contains commands, logs, links, or screenshots for the validation above.
- [ ] Reviewer questions are answered or explicitly called out as remaining decisions.
- [ ] OpenSpec or equivalent planning artifacts are archived.
- [ ] The PR is ready for the requested reviewers and the team communication channel is notified.
