# DI Pipelines Analysis

This experiment is an evidence-backed subset of
[`repository/taxonomy/data/tickets.json`](../../repository/taxonomy/data/tickets.json).
It covers only tickets with a **merged** pull request in one of these
repositories:

- `precisionlender/di-pipelines`
- `precisionlender/di-scheduling`
- `precisionlender/di-pyjobs`

## Inclusion

A ticket is included when its exact Jira key occurs in the title or description
of a merged pull request. Pull requests are stored individually, so an addendum,
fix, bugfix, or patch PR remains associated with its ticket rather than being
overwritten by a primary implementation PR.

A matching local branch is retained as supplemental evidence only. Branches do
not qualify a ticket for inclusion, because a branch alone does not show that
its work was merged.

## Data

`data/di-pipeline-tickets.json` includes the original ticket fields, sprint
history, each merged PR's name, description, author, branches, SHAs, commit
count, timestamps, and change statistics. `data/state.json` records the source
catalog, repository counts, and most recent collection time.

To refresh this experiment, ask Codex to re-read the ticket taxonomy and collect
merged PRs for these three repositories.
