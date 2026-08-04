#!/usr/bin/env bash
set -euo pipefail

ACCOUNT_NAME="${RA_ADLS_ACCOUNT:-pladls2uspreprod}"
FILE_SYSTEM="${RA_ADLS_FILESYSTEM:-datalake}"
DEFAULT_CLIENT_ID="32743a57-2030-4fa5-aadd-756ade802493"
ALPHA_AIRFLOW_BASE_URL="https://airflow.alpha01.precisionlender.com"
STAGING_ROOT=""
KEEP_STAGING=false

log() {
    printf '[%s] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*" >&2
}

usage() {
    cat <<'EOF'
Find a recent RA CSV with non-null values for the requested columns.

Usage:
  scripts/ra.sh find [client-id] --ra-file <path> --column <name> [--column <name> ...] [--days <count>] [--parallel-days <count>]

Defaults:
  client:     32743a57-2030-4fa5-aadd-756ade802493
  account:    pladls2uspreprod (override with RA_ADLS_ACCOUNT)
  filesystem: datalake (override with RA_ADLS_FILESYSTEM)
  days:       14
  parallel:   7 days at a time

Example:
  scripts/ra.sh find \
    --ra-file DatabaseOutput/dbStagingTreasuryFinancialStatementBreakdowns.csv \
    --column SomeColumn \
    --column AnotherColumn
EOF
}

require_command() {
    command -v "$1" >/dev/null || {
        echo "error: $1 is required" >&2
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

list_directories() {
    az storage fs directory list \
        --account-name "$ACCOUNT_NAME" \
        --file-system "$FILE_SYSTEM" \
        --auth-mode login \
        --path "$1" \
        --output json
}

file_exists() {
    az storage fs file exists \
        --account-name "$ACCOUNT_NAME" \
        --file-system "$FILE_SYSTEM" \
        --auth-mode login \
        --path "$1" \
        --query exists \
        --output tsv
}

download_file() {
    az storage fs file download \
        --account-name "$ACCOUNT_NAME" \
        --file-system "$FILE_SYSTEM" \
        --auth-mode login \
        --path "$1" \
        --dest "$2" \
        --output none
}

request_directories_for_day() {
    local day="$1"
    python3 -c '
import json
import sys

for entry in json.load(sys.stdin):
    leaf = entry.get("name", "").rstrip("/").rsplit("/", 1)[-1]
    if leaf.startswith(f"Request={sys.argv[1]}"):
        print(leaf)
' "$day"
}

ra_run_directories() {
    python3 -c '
import json
import sys

for entry in json.load(sys.stdin):
    leaf = entry.get("name", "").rstrip("/").rsplit("/", 1)[-1]
    if leaf.startswith("RaRun="):
        print(leaf)
'
}

find_non_null_row() {
    local csv_file="$1"
    shift

    python3 - "$csv_file" "$@" <<'PY'
import csv
import json
import sys

csv_file, *columns = sys.argv[1:]
with open(csv_file, newline="", encoding="utf-8-sig") as stream:
    reader = csv.DictReader(stream)
    headers = reader.fieldnames or []
    missing = [column for column in columns if column not in headers]
    if missing:
        print(f"missing CSV columns: {', '.join(missing)}", file=sys.stderr)
        raise SystemExit(2)

    for row in reader:
        if all((row.get(column) or "").strip() for column in columns):
            print(json.dumps({column: row[column] for column in columns}, sort_keys=True))
            raise SystemExit(0)

raise SystemExit(1)
PY
}

discover_day() {
    local day="$1"
    local request_directories_file="$2"
    local ra_file="$3"
    local client_id="$4"
    local result_file="$5"
    local data_ingress_path="ClientData/Client=$client_id/DataIngress"
    local request_directory ra_run_directory remote_file ra_run_directories_json ra_run_directories_list

    log "Starting candidate discovery for $day."
    {
        while IFS= read -r request_directory; do
            [[ -n "$request_directory" ]] || continue
            log "Inspecting $request_directory."
            ra_run_directories_json="$(list_directories "$data_ingress_path/$request_directory")"
            ra_run_directories_list="$(ra_run_directories <<<"$ra_run_directories_json")"
            while IFS= read -r ra_run_directory; do
                [[ -n "$ra_run_directory" ]] || continue
                remote_file="$data_ingress_path/$request_directory/$ra_run_directory/$ra_file"
                if [[ "$(file_exists "$remote_file")" == "true" ]]; then
                    log "Found candidate $remote_file."
                    printf '%s\n' "$remote_file"
                else
                    log "Skipping $remote_file: file does not exist."
                fi
            done <<<"$ra_run_directories_list"
        done < <(request_directories_for_day "$day" < "$request_directories_file")
    } | sort -r > "$result_file"

    log "Finished candidate discovery for $day."
}

cleanup_staging() {
    [[ "$KEEP_STAGING" == true || -z "$STAGING_ROOT" ]] || rm -rf "$STAGING_ROOT"
}

find_data() {
    local client_id="$1"
    shift
    local ra_file=""
    local days=14
    local parallel_days=7
    local columns=()

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --ra-file)
                ra_file="${2:?error: --ra-file requires a value}"
                shift 2
                ;;
            --column)
                columns+=("${2:?error: --column requires a value}")
                shift 2
                ;;
            --days)
                days="${2:?error: --days requires a value}"
                shift 2
                ;;
            --parallel-days)
                parallel_days="${2:?error: --parallel-days requires a value}"
                shift 2
                ;;
            *)
                echo "error: unknown option: $1" >&2
                exit 2
                ;;
        esac
    done

    [[ -n "$ra_file" ]] || { echo "error: --ra-file is required" >&2; exit 2; }
    [[ ${#columns[@]} -gt 0 ]] || { echo "error: at least one --column is required" >&2; exit 2; }
    [[ "$days" =~ ^[1-9][0-9]*$ ]] || { echo "error: --days must be a positive integer" >&2; exit 2; }
    [[ "$parallel_days" =~ ^[1-9][0-9]*$ ]] || { echo "error: --parallel-days must be a positive integer" >&2; exit 2; }
    require_azure_cli_user

    local data_ingress_path="ClientData/Client=$client_id/DataIngress"
    STAGING_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/ra-find.XXXXXX")"
    trap cleanup_staging EXIT
    local request_directories_file="$STAGING_ROOT/request-directories.json"
    list_directories "$data_ingress_path" > "$request_directories_file"

    log "Searching $ACCOUNT_NAME/$FILE_SYSTEM/$data_ingress_path for $ra_file over the last $days days, $parallel_days dates at a time."
    log "Temporary downloads: $STAGING_ROOT"

    local offset day batch_offset=0 result_file worker_pid worker_day remote_file relative_run candidate_directory candidate_file sample
    local discovery_directory="$STAGING_ROOT/discovery"
    local retained_directory="$STAGING_ROOT/match"
    mkdir -p "$discovery_directory" "$retained_directory"
    local -a worker_pids=() worker_days=() result_files=()
    for ((offset = 0; offset < days; offset++)); do
        day="$(python3 -c 'from datetime import date, timedelta; import sys; print(date.today() - timedelta(days=int(sys.argv[1])))' "$offset")"
        result_file="$discovery_directory/$day"
        (trap - EXIT; discover_day "$day" "$request_directories_file" "$ra_file" "$client_id" "$result_file") &
        worker_pids+=("$!")
        worker_days+=("$day")
        result_files+=("$result_file")
        ((batch_offset += 1))

        if ((batch_offset < parallel_days && offset + 1 < days)); then
            continue
        fi

        log "Waiting for ${#worker_pids[@]} date workers."
        for worker_pid in "${worker_pids[@]}"; do
            wait "$worker_pid" || true
        done

        for ((worker_day = 0; worker_day < ${#result_files[@]}; worker_day++)); do
            [[ -f "${result_files[$worker_day]}" ]] || continue
            while IFS= read -r remote_file; do
                [[ -n "$remote_file" ]] || continue
                relative_run="${remote_file#"$data_ingress_path/"}"
                relative_run="${relative_run%"/$ra_file"}"
                candidate_directory="$retained_directory/$relative_run"
                candidate_file="$candidate_directory/${ra_file##*/}"
                mkdir -p "$candidate_directory"
                log "Downloading candidate from ${worker_days[$worker_day]}: $remote_file"
                download_file "$remote_file" "$candidate_file"

                if sample="$(find_non_null_row "$candidate_file" "${columns[@]}")"; then
                    rm -rf "$discovery_directory"
                    rm -f "$request_directories_file"
                    KEEP_STAGING=true
                    log "Keeping the newest non-null match; removing discovery metadata."
                    printf 'Found non-null data in %s\n' "$remote_file"
                    printf 'Sample: %s\n' "$sample"
                    printf 'Kept local RA run: %s\n' "$candidate_directory"
                    printf 'Airflow graph: %s/dags/l3-main-%s/grid\n' "$ALPHA_AIRFLOW_BASE_URL" "$client_id"
                    return 0
                fi

                log "Rejecting $remote_file: requested columns have no shared non-null row."
                rm -rf "$candidate_directory"
            done < "${result_files[$worker_day]}"
        done

        worker_pids=()
        worker_days=()
        result_files=()
        batch_offset=0
    done

    log "No matching data found; removing temporary downloads."
    echo "No non-null example found in the last $days days." >&2
    return 1
}

main() {
    require_command az
    require_command python3

    case "${1:-}" in
        find)
            shift
            if [[ ${1:-} == --* || $# -eq 0 ]]; then
                find_data "$DEFAULT_CLIENT_ID" "$@"
            else
                find_data "$1" "${@:2}"
            fi
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
