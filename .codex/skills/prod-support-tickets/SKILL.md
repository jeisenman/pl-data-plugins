---
name: prod-support-tickets
description: Prepare a Jira ticket recommendation for a production Airflow task that has failed after five or more attempts. Use after production-support log triage identifies a repeated exhausted failure, or when asked to create, draft, review, parent, estimate, or assign a production-support investigation ticket. Never create or modify a Jira ticket without the user's explicit approval.
---

# Prod Support Tickets

Prepare a complete ticket proposal for repeated production failures. This skill is a
suggested outcome, not an automatic remediation.

## Qualifying failure

1. Start from production-support discovery and final-attempt log evidence.
2. Qualify only when the same task instance is `failed` after five or more attempts
   (`try_number >= 5`). Count actual attempts, not repeated observations of the
   same task instance.
3. Do not propose a ticket when the failure is a validated distinctness rerun,
   a recoverable EventBus resend, an ignored canary, or a known recurring issue
   with no new signal, unless the user requests a ticket anyway.
4. For any other qualifying failure, add a concise ticket recommendation to the
   developer report. State that the ticket is **not created**.

## Prepare the recommendation

Use the `triage-issue` skill to search the Data Engineering Jira project for exact
task names, error signatures, and related resolved issues. Treat a closed issue as
historical context, not as proof that the new failure is a duplicate.

Include only verified evidence:

- affected client name and full UUID;
- region, DAG ID, task ID, failed run, and final attempt count;
- exact failure signature (for example `BlobNotFound`, `-9`, or a validation error);
- safe rerun recommendation, or explicitly say that none was validated;
- related Jira issues and their status.

Default the proposal to a Data Engineering `Task`, using the current user's account
only when the user names themselves or Jira confirms that identity. Do not infer an
assignee from a display-name match when multiple users match.

## Parent, sprint, and estimate

When a parent is requested, inspect the current `PL Production Support - Sprint`
Jira work item. Use its active sprint and parent only after verifying them in Jira.
For a PrecisionLender production-support ticket, mirror its verified product bucket,
team, and support/maintenance classification when those fields are required.

If requested, use Outlook read-only search for Jira notifications from Holger Trinks
to confirm historical parent-assignment practice. Jira's current support ticket is
authoritative for the current parent.

## Approval boundary

Before any Jira write, present the proposed summary, parent, sprint, assignee, estimate,
and evidence. Ask for explicit approval to create or update the exact ticket.

Do not create, edit, link, assign, estimate, or parent a Jira issue from the qualifying
failure alone. On approval, verify required Jira fields, perform only the approved write,
then re-read the issue to confirm the requested values.
