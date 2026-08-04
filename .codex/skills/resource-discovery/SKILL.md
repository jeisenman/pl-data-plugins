---
name: resource-discovery
description: Query the PrecisionLender Resource Discovery API for client names, client GUIDs, environments, database servers, databases, storage, and DataLake resources. Use only the Resource Discovery API, not local repository search, when asked to look up client resources.
---

# Resource Discovery

Use this skill to query the internal Resource Discovery API. Do not search local repositories for this skill; Resource Discovery API responses are the authoritative source.

## Workflow

1. Clarify the identifier only when needed. Useful identifiers include client UUID, client name, subdomain, resource set, environment, database, storage account, or DataLake account.
2. Call the API helper:

   ```bash
   python3 .codex/skills/resource-discovery/scripts/resource_discovery_api.py /api/v1/clients --query provisionedClientId=<client-uuid>
   ```

3. For other read-only endpoints, pass the API path and any query parameters:

   ```bash
   python3 .codex/skills/resource-discovery/scripts/resource_discovery_api.py /api/v1/resources --query name=<resource-name>
   ```

4. Summarize only non-secret fields returned by the API. Never print access tokens, client secrets, or raw credential values.
5. If the API returns multiple records, report each one and call out the ambiguity rather than choosing silently.

Never write client secrets to tracked repository files, command history snippets, logs, or final answers. Keep local values in ignored `.env` under `# resource discovery`, or supply them through the current shell session.

## Internal API

The Resource Discovery API uses Azure AD client credentials. Use `scripts/resource_discovery_api.py` for token acquisition and read-only GET requests. The script reads ignored `.env` by default and accepts these environment variables:

- `RESOURCE_DISCOVERY_CLIENT_ID` - required.
- `RESOURCE_DISCOVERY_CLIENT_SECRET` - required.
- `RESOURCE_DISCOVERY_TENANT_ID` - required.
- `RESOURCE_DISCOVERY_SCOPE` - required.
- `RESOURCE_DISCOVERY_BASE_URL` - required.

## Common API Calls

Client by provisioned PrecisionLender client UUID:

```bash
python3 .codex/skills/resource-discovery/scripts/resource_discovery_api.py /api/v1/clients --query provisionedClientId=<client-uuid>
```

Resources:

```bash
python3 .codex/skills/resource-discovery/scripts/resource_discovery_api.py /api/v1/resources
```

## Report Shape

Return a concise answer with:

- `Finding`: the direct API answer.
- `Resource Discovery`: client name, provisioned client ID, subdomain, environment, zone, service, resource set, database, storage, and DataLake fields when present.
- `Ambiguities`: multiple API records, missing records, or the identifier needed to disambiguate.
