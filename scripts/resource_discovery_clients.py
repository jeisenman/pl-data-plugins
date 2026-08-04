#!/usr/bin/env python3
"""List clients and data-isolation metadata from Resource Discovery/Contx.

Credentials are read from environment variables. The script intentionally prints
only non-secret client and datastore fields returned by the API.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import Request, urlopen


DEFAULT_SCOPE = "api://resourcediscovery-internal.precisionlender.com/.default"
DEFAULT_DATASTORES = (
    "HistoricalDataMartADLS",
    "InternalDataMartADLS",
    "MarketInsightsDataMartADLS",
    "OMSLoggingApi",
    "ModelsHistoricalDataMartADLS",
    "Snowflake",
    "ClientDataMartADLS",
    "OperationalADLS",
    "PLBlobStorage",
)

CLIENTS_DATA_STORES_QUERY = """
mutation ClientsDataStores($RequestMetadata: ClientsDataStoresContextInput) {
  client_data_stores(arguments: $RequestMetadata) {
    client_id
    client_is_data_isolated
    data_stores {
      name
      kind
      strategy
      protocol
      host_name
      domain
      path
      database
      region
      groups
      tags
      is_data_isolated
    }
  }
}
"""


def post_json(url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Accept": "application/json", "Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {url}: {body[:1000]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not reach {url}: {exc.reason}") from exc

    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Non-JSON response from {url}: {body[:1000]}") from exc


def get_access_token(tenant_id: str, client_id: str, client_secret: str, scope: str) -> str:
    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    form = urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": scope,
            "grant_type": "client_credentials",
        }
    ).encode("utf-8")
    request = Request(
        token_url,
        data=form,
        headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OAuth HTTP {exc.code}: {body[:1000]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not reach Microsoft token endpoint: {exc.reason}") from exc

    token = payload.get("access_token")
    if not token:
        raise RuntimeError(f"OAuth response did not contain access_token: {payload}")
    return token


def graphql(base_url: str, token: str, variables: dict[str, Any]) -> dict[str, Any]:
    endpoint = base_url if urlparse(base_url).path else urljoin(base_url, "graphql")
    payload = post_json(
        endpoint,
        {"operationName": "ClientsDataStores", "query": CLIENTS_DATA_STORES_QUERY, "variables": variables},
        {"Authorization": f"Bearer {token}"},
    )
    if payload.get("errors"):
        raise RuntimeError(json.dumps(payload["errors"], indent=2))
    return payload.get("data", {})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.getenv("RESOURCE_DISCOVERY_BASE_URL", "https://resourcediscovery-internal.precisionlender.com/graphql"))
    parser.add_argument("--scope", default=os.getenv("RESOURCE_DISCOVERY_SCOPE", DEFAULT_SCOPE))
    parser.add_argument("--client-id", help="Return only this client ID")
    parser.add_argument("--shared-group", action="append", dest="shared_groups", help="Restrict results to one or more shared groups")
    parser.add_argument("--datastore", action="append", dest="datastores", help="Datastore kind; repeat for multiple kinds")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    required = ("RESOURCE_DISCOVERY_CLIENT_ID", "RESOURCE_DISCOVERY_CLIENT_SECRET", "RESOURCE_DISCOVERY_TENANT_ID")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        print(f"Missing environment variables: {', '.join(missing)}", file=sys.stderr)
        return 2

    token = get_access_token(
        tenant_id=os.environ["RESOURCE_DISCOVERY_TENANT_ID"],
        client_id=os.environ["RESOURCE_DISCOVERY_CLIENT_ID"],
        client_secret=os.environ["RESOURCE_DISCOVERY_CLIENT_SECRET"],
        scope=args.scope,
    )
    request_metadata: dict[str, Any] = {
        "application_name": "precisionlender",
        "data_stores": args.datastores or list(DEFAULT_DATASTORES),
    }
    if args.shared_groups:
        request_metadata["shared_group_names"] = args.shared_groups

    clients = graphql(args.base_url, token, {"RequestMetadata": request_metadata}).get("client_data_stores", [])
    if args.client_id:
        clients = [client for client in clients if client.get("client_id") == args.client_id]
    print(json.dumps(clients, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
