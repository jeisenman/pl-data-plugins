#!/usr/bin/env python3
"""Measure L3 Historical DatePartition sizes through the Azure CLI (read-only)."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timedelta


GIB = 1024 ** 3


def az_json(*args: str) -> object:
    command = ["az", "storage", "fs", *args, "--auth-mode", "login", "--output", "json"]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def paths(*args: str) -> list[dict[str, object]]:
    """Return every page from `az storage fs file list`."""
    marker: str | None = None
    entries: list[dict[str, object]] = []
    while True:
        page_args = [*args, "--show-next-marker"]
        if marker:
            page_args.extend(("--marker", marker))
        value = az_json(*page_args)
        if isinstance(value, list):
            return entries + value
        if not isinstance(value, dict) or not isinstance(value.get("paths"), list):
            raise RuntimeError("Azure CLI returned an unexpected file-list response")
        entries.extend(value["paths"])
        marker = value.get("nextMarker")
        if not marker:
            return entries


def partition_date(path: str) -> datetime | None:
    marker = "DatePartition="
    if marker not in path:
        return None
    value = path.rsplit(marker, 1)[1].strip("/")
    for pattern in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, pattern)
        except ValueError:
            pass
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account", required=True, help="ADLS storage account hosting l3-historical")
    parser.add_argument("--path", required=True, help="Dataset root through VersionPartition=..., without DatePartition")
    parser.add_argument("--filesystem", default="l3-historical")
    parser.add_argument("--days", type=int, default=31)
    parser.add_argument("--as-of", help="UTC date YYYY-MM-DD; defaults to today")
    args = parser.parse_args()
    if args.days < 1:
        parser.error("--days must be positive")
    as_of = datetime.strptime(args.as_of, "%Y-%m-%d") if args.as_of else datetime.utcnow()
    cutoff = as_of - timedelta(days=args.days)
    root = args.path.strip("/")
    children = az_json("directory", "list", "--account-name", args.account, "--file-system", args.filesystem, "--path", root, "--recursive", "false")
    if not isinstance(children, list):
        raise RuntimeError("Azure CLI returned an unexpected directory-list response")
    partitions = []
    for child in children:
        name = str(child.get("name", "")).rstrip("/")
        parsed = partition_date(name)
        if parsed and parsed >= cutoff:
            partitions.append((parsed, name))
    sizes: list[tuple[datetime, str, int]] = []
    for parsed, partition in sorted(partitions):
        files = paths("file", "list", "--account-name", args.account, "--file-system", args.filesystem, "--path", partition, "--recursive", "true")
        total = sum(int(item.get("contentLength") or 0) for item in files if not item.get("isDirectory", False))
        sizes.append((parsed, partition, total))
    if not sizes:
        raise RuntimeError(f"no DatePartition directories found on or after {cutoff:%Y-%m-%d}")
    for parsed, partition, total in sizes:
        print(f"{parsed:%Y-%m-%d}\t{total / GIB:.2f} GiB\t{partition}")
    largest = max(sizes, key=lambda item: item[2])
    latest = max(sizes, key=lambda item: item[0])
    print(f"partitions={len(sizes)}")
    print(f"largest_gib={largest[2] / GIB:.2f}\tlargest_partition={largest[1]}")
    print(f"latest_gib={latest[2] / GIB:.2f}\tlatest_partition={latest[1]}")
    print(f"total_gib={sum(item[2] for item in sizes) / GIB:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
