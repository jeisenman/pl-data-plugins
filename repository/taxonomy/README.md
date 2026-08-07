# Jira Ticket Taxonomy

`data/tickets.json` is the local ticket catalog. It is keyed by Jira issue key and
contains the current ticket fields plus every tracked board/sprint assignment.
`data/state.json` records the tracked sprint window for each board and the last
successful update.

## Updating the catalog

The catalog is maintained through the authenticated Atlassian connection available
to Codex. It does not use a local Jira REST client or require an API token.

Ask Codex to backfill or update the catalog, for example:

```text
Backfill the last 13 sprints for Jordan Eisenman on Data Platform and PL Data.
```

```text
Update the Jira taxonomy for the latest sprints.
```

The update should re-read the newest tracked sprints and any newly completed or
active sprint, refresh ticket fields, and update `last_updated` only after the
snapshot has been written successfully.
