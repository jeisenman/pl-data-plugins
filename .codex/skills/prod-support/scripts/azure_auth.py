"""Authenticate Azure CLI with the production data-engineering identity."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


ROLE = "data-engineering"
REQUIRED_VARS = (
    "DATA_ENGINEERING_AZURE_CLIENT_ID",
    "DATA_ENGINEERING_AZURE_CLIENT_SECRET",
    "DATA_ENGINEERING_AZURE_TENANT_ID",
)


def load_dotenv(env_file: Path = Path(".env")) -> None:
    """Load local credentials without overriding explicitly exported values."""
    if not env_file.is_file():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key.isidentifier() or key in os.environ:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ[key] = value


def ensure_azure_login(*, dry_run: bool = False) -> bool:
    """Log Azure CLI in as the data-engineering service principal, without secrets."""
    load_dotenv()
    missing = [name for name in REQUIRED_VARS if not os.environ.get(name)]
    if missing:
        print(
            f"Missing Azure {ROLE} environment variable(s): " + ", ".join(missing),
            file=sys.stderr,
        )
        return False
    if not shutil.which("az"):
        print("az is not available; install Azure CLI before resource discovery.", file=sys.stderr)
        return False

    command = [
        "az", "login", "--service-principal",
        "--username", os.environ["DATA_ENGINEERING_AZURE_CLIENT_ID"],
        "--password", os.environ["DATA_ENGINEERING_AZURE_CLIENT_SECRET"],
        "--tenant", os.environ["DATA_ENGINEERING_AZURE_TENANT_ID"],
        "--output", "none",
    ]
    if dry_run:
        print(
            '+ az login --service-principal '
            '--username "$DATA_ENGINEERING_AZURE_CLIENT_ID" '
            '--password "$DATA_ENGINEERING_AZURE_CLIENT_SECRET" '
            '--tenant "$DATA_ENGINEERING_AZURE_TENANT_ID" --output none'
        )
        return True
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode:
        print(f"Azure service-principal login failed: {result.stderr.strip()}", file=sys.stderr)
        return False
    print("Authenticated Azure CLI as data-engineering.")
    return True
