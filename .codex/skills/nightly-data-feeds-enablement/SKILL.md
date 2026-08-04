---
name: nightly-data-feeds-enablement
description: Enable provisioned PrecisionLender clients in the nightly data-feeds pipeline. Use when a client is ready for nightly data feeds in US01 or another stack and must be added, activated, or checked in di-scheduling production Contx metadata.
---

# Nightly Data Feeds Enablement

## Verify the request

1. Obtain the Jira ticket key, client ID, target stack, and confirmation that the client is already provisioned.
2. Search the target environment metadata for the client ID and client name. Do not create a datastore or client group solely for a nightly-feed request.
3. Confirm the client is not already active in `Deployment/ContxMetadata/production/application_partitions.json`.

## Add the production partition

1. Work in the requested `di-scheduling` worktree on a branch named exactly for the Jira ticket key, such as `DE-3028`.
2. Add one active `precisionlender` application partition for the client.
3. For US01, use `zone: "us"`, `shared_group: "pl-us-dipipeline-prod-01b"`, `is_data_isolated: false`, and `data_rights_tier: 3` unless the provisioning record specifies an exception.
- Check https://resourcediscovery.precisionlender.com/#/resourcefinder.
- Enter the client guuid into Select a client.
- If client has own environment that is not US01, US02, or CA, then `is_data_isolated: true`. Else, `data_rights_tier: 1`
- If client in US01, US02, or CA -- then `is_data_isolated: true`. Else, `data_rights_tier: 2`
- If client doesn't have unique database, then `is_data_isolated: false`. Else, `data_rights_tier: 3`

4. Use the existing client group only when it is present 


in the provisioning metadata; otherwise use `null`.

## Validate and publish

1. Verify the diff adds exactly one intended application-partition entry and does not change unrelated metadata.
2. Commit with the Jira ticket key, push that same Jira-key branch, and record the deployment follow-up. Do not create a feature-named branch when a ticket key is available.

Leave PR description:
[DE-###](https://qtwo.atlassian.net/jira/software/c/projects/DE/boards/5705?assignee=712020%3A646f8ce2-209c-4122-b079-8f1e3d3f3bdd&selectedIssue=DE-####)
[Bank Name] is now provisioned on [US01, US02, ETC] and they need to be added to the night feeds. 

Client ID: {GUUID}

Client Name: {Full Name}

Stack: {Stack}