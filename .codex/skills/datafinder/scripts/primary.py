#!/usr/bin/env python3
"""Resolve primary metadata to DataStudioHistorical paths and find non-null rows."""

from __future__ import annotations

import argparse
import ast
import csv
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


ACCOUNTS = {
    "alpha": "pladls2usdatamartalpha01",
    "staging": "pladls2usdatamartprodt",
}
DEFAULT_FILESYSTEM = "l3-historical"


@dataclass
class Dataset:
    alias: str
    stage: str
    provider: str
    group: str
    name: str
    version: str
    file_format: str = "csv"
    columns: list[str] = field(default_factory=list)

    def path(self, client_id: str) -> str:
        return (
            f"ClientId={client_id}/L3/v1.0/{self.stage}/{self.provider}/{self.group}/{self.name}/"
            f"InstancePartition={client_id}/VersionPartition={self.version}"
        )


def literal_assignments(class_node: ast.ClassDef) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for statement in class_node.body:
        if isinstance(statement, (ast.Assign, ast.AnnAssign)):
            targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
            value_node = statement.value
            for target in targets:
                if isinstance(target, ast.Name) and value_node is not None:
                    try:
                        values[target.id] = ast.literal_eval(value_node)
                    except (ValueError, TypeError):
                        pass
    return values


def metadata_dataset(spec: str) -> Dataset:
    try:
        filename, class_name = spec.rsplit(":", 1)
    except ValueError as exc:
        raise ValueError("--metadata must be FILE:CLASS") from exc
    source = Path(filename)
    module = ast.parse(source.read_text(), filename=str(source))
    class_node = next((node for node in module.body if isinstance(node, ast.ClassDef) and node.name == class_name), None)
    if class_node is None:
        raise ValueError(f"class {class_name!r} not found in {source}")
    values = literal_assignments(class_node)
    required = ["PATH_STAGE", "PATH_PROVIDER", "PATH_GROUP", "DATASET_NAME", "LATEST_MAJOR_VERSION", "LATEST_MINOR_VERSION"]
    missing = [name for name in required if name not in values]
    if missing:
        raise ValueError(f"{class_name} is missing literal metadata constants: {', '.join(missing)}")
    return Dataset(
        alias=class_name,
        stage=str(values["PATH_STAGE"]),
        provider=str(values["PATH_PROVIDER"]),
        group=str(values["PATH_GROUP"]),
        name=str(values["DATASET_NAME"]),
        version=f"v{values['LATEST_MAJOR_VERSION']}.{values['LATEST_MINOR_VERSION']}",
    )


def explicit_dataset(spec: str) -> Dataset:
    try:
        alias, value = spec.split("=", 1)
        path, version = value.rsplit("@", 1)
        parts = path.strip("/").split("/")
        if len(parts) == 3:
            stage, (provider, group, name) = "Primary", parts
        elif len(parts) == 4:
            stage, provider, group, name = parts
        else:
            raise ValueError
    except ValueError as exc:
        raise ValueError("--dataset must be ALIAS=[STAGE/]PROVIDER/GROUP/NAME@vMAJOR.MINOR") from exc
    if not version.startswith("v"):
        version = f"v{version}"
    return Dataset(alias, stage, provider, group, name, version)


def attach_columns(datasets: dict[str, Dataset], specs: list[str]) -> None:
    for spec in specs:
        try:
            alias, column = spec.split(":", 1)
        except ValueError as exc:
            raise ValueError("--column must be DATASET_ALIAS:COLUMN") from exc
        if alias not in datasets:
            raise ValueError(f"unknown dataset alias {alias!r}; expected one of: {', '.join(datasets)}")
        datasets[alias].columns.append(column)
    without_columns = [dataset.alias for dataset in datasets.values() if not dataset.columns]
    if without_columns:
        raise ValueError(f"at least one --column is required for: {', '.join(without_columns)}")


def az_json(account: str, filesystem: str, *args: str) -> Any:
    command = ["az", "storage", "fs", *args, "--account-name", account, "--file-system", filesystem, "--auth-mode", "login", "--output", "json"]
    return json.loads(subprocess.check_output(command, text=True))


def require_azure_cli_user() -> None:
    """Require a human Azure CLI login; never fall back to a service principal."""
    result = subprocess.run(
        ["az", "account", "show", "--output", "json"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        detail = result.stderr.strip() or "Azure CLI is not signed in."
        raise RuntimeError(
            "primary find requires an Azure CLI Data Engineer user login; "
            "run `az login --use-device-code` first. "
            f"Azure CLI reported: {detail}"
        )
    try:
        account = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Azure CLI returned an invalid account response.") from exc
    if account.get("user", {}).get("type") != "user":
        raise RuntimeError(
            "primary find requires an Azure CLI Data Engineer user login, not a service principal; "
            "run `az login --use-device-code` first."
        )


def list_paths(account: str, filesystem: str, path: str) -> list[dict[str, Any]]:
    return az_json(account, filesystem, "directory", "list", "--path", path)


def download(account: str, filesystem: str, remote: str, destination: Path) -> None:
    command = [
        "az", "storage", "fs", "file", "download", "--account-name", account,
        "--file-system", filesystem, "--auth-mode", "login", "--path", remote,
        "--dest", str(destination), "--output", "none",
    ]
    subprocess.run(command, check=True)


def non_null_sample(path: Path, columns: list[str]) -> dict[str, Any] | None:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            missing = [column for column in columns if column not in (reader.fieldnames or [])]
            if missing:
                return None
            for row in reader:
                if all(row.get(column) not in (None, "") for column in columns):
                    return {column: row[column] for column in columns}
        return None
    if suffix in {".parquet", ".pq"}:
        import pyarrow.dataset as ds

        table = ds.dataset(path, format="parquet").to_table(columns=columns)
        for row in table.to_pylist():
            if all(row.get(column) is not None for column in columns):
                return row
        return None
    return None


def leaves(entries: list[dict[str, Any]], prefix: str) -> list[str]:
    return sorted(
        (entry.get("name", "").rstrip("/") for entry in entries if entry.get("name", "").rstrip("/").split("/")[-1].startswith(prefix)),
        reverse=True,
    )


def find_dataset(dataset: Dataset, client_id: str, account: str, filesystem: str, partitions: int) -> dict[str, Any] | None:
    root = dataset.path(client_id)
    date_paths = leaves(list_paths(account, filesystem, root), "DatePartition=")[:partitions]
    with tempfile.TemporaryDirectory(prefix="primary-find-") as temp_dir:
        for date_path in date_paths:
            entries = list_paths(account, filesystem, date_path)
            files = [entry.get("name", "") for entry in entries if not entry.get("isDirectory", False)]
            for remote in files:
                suffix = Path(remote).suffix.lower()
                if suffix not in {".csv", ".parquet", ".pq"}:
                    continue
                local = Path(temp_dir) / Path(remote).name
                download(account, filesystem, remote, local)
                sample = non_null_sample(local, dataset.columns)
                if sample is not None:
                    return {"path": remote, "columns": dataset.columns, "sample": sample}
    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("resolve", "find"):
        sub = subparsers.add_parser(command)
        sub.add_argument("--client", required=True, help="Client UUID")
        sub.add_argument("--environment", choices=sorted(ACCOUNTS), default="alpha")
        sub.add_argument("--account", help="Override the environment storage account")
        sub.add_argument("--filesystem", default=DEFAULT_FILESYSTEM)
        sub.add_argument("--metadata", action="append", default=[], metavar="FILE:CLASS")
        sub.add_argument("--dataset", action="append", default=[], metavar="ALIAS=PROVIDER/GROUP/NAME@vX.Y")
        sub.add_argument("--column", action="append", default=[], metavar="ALIAS:COLUMN")
        if command == "find":
            sub.add_argument("--partitions", type=int, default=14, help="Newest DatePartitions to inspect")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        resolved = [metadata_dataset(spec) for spec in args.metadata] + [explicit_dataset(spec) for spec in args.dataset]
        if not resolved:
            raise ValueError("at least one --metadata or --dataset is required")
        datasets = {dataset.alias: dataset for dataset in resolved}
        if len(datasets) != len(resolved):
            raise ValueError("dataset aliases must be unique")
        attach_columns(datasets, args.column)
    except (OSError, SyntaxError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    account = args.account or ACCOUNTS[args.environment]
    output = {
        "client": args.client,
        "environment": args.environment,
        "account": account,
        "filesystem": args.filesystem,
        "datasets": [dict(vars(dataset), path=dataset.path(args.client)) for dataset in datasets.values()],
    }
    if args.command == "find":
        try:
            require_azure_cli_user()
        except RuntimeError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        output["results"] = {
            alias: find_dataset(dataset, args.client, account, args.filesystem, args.partitions)
            for alias, dataset in datasets.items()
        }
    print(json.dumps(output, indent=2, default=str))
    return 0 if args.command == "resolve" or all(output["results"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
