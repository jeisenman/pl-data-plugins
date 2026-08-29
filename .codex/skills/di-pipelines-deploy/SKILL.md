---
name: di-pipelines-deploy
description: Deploy a di-pipelines ticket branch to Alpha or, when requested, through Alpha to Staging via the Azure DevOps di-pipelines-unified pipeline. Use for prompts such as "deploy DE-1234", "deploy DE-1234 staging", or a dry-run deployment preflight.
---

# DI Pipelines Deploy

Run this workflow through the `DI Pipelines Deploy` role in
`.codex/agents/di-pipelines-deploy.toml`. It uses `gpt-5.6-luna` with high
reasoning effort. If the current agent is not that role and can delegate, hand
the complete request to it.

## Inputs and modes

Accept these prompt forms:

- `deploy DE-1234` — deploy the ticket branch to Alpha.
- `deploy DE-1234 staging` — deploy the ticket branch to Alpha, then Staging.
- Append `--dry-run` to perform the complete read-only preflight without sending
  Slack messages, creating an Azure run, or approving a gate.

Require one exact ticket identifier matching `DE-<digits>`. Treat any target
other than `staging` as Alpha. Never deploy production, change a pipeline
definition, merge code, or select a different ticket branch.

## Resolve the branch

1. Confirm the selected repository or worktree is `di-pipelines` by inspecting
   its Git root and remote.
2. Resolve the ticket to exactly one branch. Prefer the current branch only when
   it contains the requested ticket identifier. Otherwise inspect local and
   `origin` branch refs for a single branch containing it.
3. Stop if no branch matches, multiple branches match, HEAD is detached, or the
   repository/worktree is ambiguous. Do not guess from a pull request or ticket
   title.
4. Record the exact branch ref that Azure DevOps displays and use it unchanged.

## Coordinate Alpha in Slack

Skip all Slack writes in `--dry-run`; still read the channel and report the
resulting deployment-ownership decision.

In the `Data Internal` channel, find today's `Deployments` thread using the
`America/New_York` date. Read it chronologically and resolve people by Slack
identity rather than display-name similarity.

- Continue when Jordan Eisenman has an active `taking alpha`, `taking`, or
  equivalent claim.
- Continue when nobody has an active claim, or the most recent claimant said
  `done`, `finished`, or an unambiguous equivalent.
- Stop without changing Slack or Azure when someone else has an unresolved
  active claim, or when the thread, sender, or completion state is ambiguous.

When Alpha is free, search the full thread for Jordan Eisenman's prior claim. If
none exists, reply exactly `Taking alpha`. Do not create a replacement thread or
duplicate claim. Re-read after posting and continue only if no later conflicting
claim appears.

## Queue and approve Alpha

In the user's authenticated Chrome session:

1. Open `https://dev.azure.com/precisionlender/Data%20Engineering/_build`.
2. Open `di-pipelines-unified`, select `New run`, and set the exact resolved
   branch/ref.
3. Select `Next: Resources`; verify the pipeline name and branch.
4. In a live run, select `Run` once and capture its URL/identifier. If the UI is
   uncertain, inspect existing runs before retrying.
5. In `--dry-run`, stop after recording the verified intended pipeline and
   branch; do not select `Run`.

For every queued run, inspect the stage graph. Approve only an enabled gate that
belongs to this run, is required for the Alpha path, and visibly targets Alpha
or an unambiguous non-production Alpha prerequisite. Never approve a production
or ambiguous gate. Do not reject, cancel, retry, or bypass a check.

Refresh at 45-second intervals while further required Alpha gates can become
available. Run the wait helper between checks:

```bash
python3 .codex/skills/di-pipelines-deploy/scripts/wait.py 45
```

Record each approval, avoid duplicate submissions, and finish the Alpha-only
workflow when all required Alpha approvals have been submitted. The pipeline
need not finish unless Staging was requested.

## Continue to Staging

Run this section only for `deploy DE-1234 staging` after all required Alpha
approvals have been submitted.

1. Confirm the same run's Alpha path has passed and the Staging path is next.
   Stop if Alpha fails, is canceled, is rejected, or the target is ambiguous.
2. Wait 11 minutes for the deployment tests. Do not shorten this initial wait:

   ```bash
   python3 .codex/skills/di-pipelines-deploy/scripts/wait.py 660
   ```

3. Then inspect the run every 45 seconds until the required tests pass or a
   terminal failure/blocker appears. Use the same wait helper with `45` between
   checks. Stop on failure, cancellation, rejection, unavailable access, or an
   ambiguous target.
4. Once the tests pass and the Staging deployment requires approval, post this
   exact message in the `Data Internal` channel:

   `Deploying DE-1234. Please approve <URL_OF_DEPLOYMENT>.`

   Replace `DE-1234` with the requested ticket and the placeholder with the
   direct Azure deployment/run URL. Do not post this message in `--dry-run`.
5. Approve only the enabled, required Staging gate of this same run when its
   target visibly says Staging. Continue at 45-second intervals until all
   required Staging approvals have been submitted.

## Report

Return the ticket, resolved branch, requested target, run URL, Slack action (or
the messages suppressed by dry-run), approvals submitted, and final observed
state. Distinguish `all required approvals submitted` from `pipeline completed`.
