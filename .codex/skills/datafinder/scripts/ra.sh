#!/usr/bin/env bash
set -euo pipefail

ACCOUNT_NAME="${RA_ADLS_ACCOUNT:-pladls2uspreprod}"
FILE_SYSTEM="${RA_ADLS_FILESYSTEM:-datalake}"

usage() {
    cat <<'EOF'
Usage:
  scripts/ra.sh root
  scripts/ra.sh ls [path]
  scripts/ra.sh client <client-id>
  scripts/ra.sh request <client-id> <request-directory>
  scripts/ra.sh run <client-id> <request-directory> <run-directory>

Defaults:
  account:    pladls2uspreprod (override with RA_ADLS_ACCOUNT)
  filesystem: datalake (override with RA_ADLS_FILESYSTEM)

Examples:
  scripts/ra.sh client 32743a57-2030-4fa5-aadd-756ade802493
  scripts/ra.sh run 32743a57-2030-4fa5-aadd-756ade802493 Request=2026-08-03-12-00 RaRun=2026-08-03-12-00
EOF
}

require_az() {
    command -v az >/dev/null || {
        echo "error: Azure CLI (az) is required" >&2
        exit 1
    }
}

require_azure_cli_user() {
    local login_type
    if ! login_type="$(az account show --query user.type --output tsv 2>/dev/null)"; then
        echo "error: RA discovery requires an Azure CLI Data Engineer user login; run az login --use-device-code first" >&2
        exit 1
    fi
    if [[ "$login_type" != "user" ]]; then
        echo "error: RA discovery requires an Azure CLI Data Engineer user login, not a service principal; run az login --use-device-code first" >&2
        exit 1
    fi
}

list_directory() {
    local path="$1"
    local args=(
        storage fs directory list
        --account-name "$ACCOUNT_NAME"
        --file-system "$FILE_SYSTEM"
        --auth-mode login
        --output table
    )

    if [[ -n "$path" ]]; then
        args+=(--path "$path")
    fi

    require_azure_cli_user
    az "${args[@]}"
}

main() {
    require_az

    case "${1:-}" in
        root)
            [[ $# -eq 1 ]] || { usage >&2; exit 2; }
            list_directory ""
            ;;
        ls)
            [[ $# -le 2 ]] || { usage >&2; exit 2; }
            list_directory "${2:-}"
            ;;
        client)
            [[ $# -eq 2 ]] || { usage >&2; exit 2; }
            list_directory "ClientData/Client=$2/DataIngress"
            ;;
        request)
            [[ $# -eq 3 ]] || { usage >&2; exit 2; }
            list_directory "ClientData/Client=$2/DataIngress/$3"
            ;;
        run)
            [[ $# -eq 4 ]] || { usage >&2; exit 2; }
            list_directory "ClientData/Client=$2/DataIngress/$3/$4"
            ;;
        -h|--help|help|"")
            usage
            ;;
        *)
            echo "error: unknown command: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
}

main "$@"
