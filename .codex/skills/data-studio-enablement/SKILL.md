---
name: data-studio-enablement
description: "Requirements for enabling Data Studio UUX Client Reader Account."
ruleset_id: "DATASTUDIOENABLEMENT"
scope:
  - "repositories/di-pipelines/*/de-jobs/src/datamart/jobs/snowflake/metadata/shares.py"
  - "repositories/di-pipelines/"
type: engineering-rule
---

# Data Studio Adding Reader Account

## Scope

- The authoritative scope is the frontmatter scope field.
- Your responsibility is to a) look at open Jira tickets for the current sprint and b) to make git worktree branch DE-#### based on the Jira ticket identifier
- Based on ticket and possible prompt, find the relevant GitLab logs and properly append the reader accounts to one of the `DataStudioSnowflakeClientDetails` within `repositories/di-pipelines/*/de-jobs/src/datamart/jobs/snowflake/metadata/shares.py`.

## Requirements

- If activating client:
1. Find relevant Jira ticket identifying the relevant ticket number DE-####, instance partition GUUID, and code environment -- [alpha, staging, prod]. 
2. If account locator is not found on the ticket, run the `.codex/skills/data-studio-enablement/scripts/reader_accounts_pipeline.sh`. Pattern match to find the relevant account locator.
3. Append new record to  `{ENV}_DATA_STUDIO_UUX_CLIENT_SHARES` in format:
```
DataStudioSnowflakeClientDetail(
    instance_partition=GUUID,
    account_locator="{ACCOUNT_LOCATOR},
    is_active=True,
),
```
4. Create PR with description format
```[txt]
Ticket: [DE-####](https://qtwo.atlassian.net/browse/DE-####)

We need to add {BANK_NAME} with {INSTANCE_PARTITION}` to {ENVIRONMENT}. We can find the GitLab pipeline URL here:
- {url_to_relevant_pipeline}

The client details should match:
- {GUUID}
- [alpha,staging,prod]
- {account_locator}
```


- If de-activating client:
1. If account locator is not found on the ticket, run the `.codex/skills/data-studio-enablement/scripts/reader_accounts_pipeline.sh`. Pattern match to find the relevant account locator.
2. Set `is_active=False`
```
DataStudioSnowflakeClientDetail(
    instance_partition=GUUID,
    account_locator="{ACCOUNT_LOCATOR},
    is_active=True,
),
```
Do not delete the record!

Compliant

~~~python
PROD_DATA_STUDIO_UUX_CLIENT_SHARES = DataStudioSnowflakeClientDetails(
    client_details=[
        DataStudioSnowflakeClientDetail(
            instance_partition="{GUUID}",
            account_locator="{ACCOUNT_LOCATOR}",
            is_active=True,
        )
    ],
)


~~~

Violation
- Removing value!
~~~python
PROD_DATA_STUDIO_UUX_CLIENT_SHARES = DataStudioSnowflakeClientDetails(
    client_details=[
    ],
)
~~~

Finally, provide message to me: PR exists here: {url_to_pr}
