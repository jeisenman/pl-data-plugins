#!/usr/bin/env bash
set -euo pipefail

readonly DEFAULT_REPO='q2e/it/terraform/snowflake/q2e/projects/managed-customer-accounts/reader-accounts-creation'
readonly DEFAULT_REF='develop'

repo="$DEFAULT_REPO"
ref="$DEFAULT_REF"
pipeline_id=''
trace_job=''
id_only=false
reader_accounts_only=false

usage() {
  cat <<'EOF'
Usage: reader_accounts_pipeline.sh [options]

Show the latest reader-accounts-creation pipeline for a GitLab ref and its jobs.

Options:
  --ref REF             Git ref to inspect (default: develop).
  --repo NAMESPACE/PROJECT
                        GitLab project (default: reader-accounts-creation).
  --pipeline-id ID      Inspect this pipeline instead of resolving the latest one.
  --trace JOB           Stream the trace for a job name or job ID in the pipeline.
  --apply-production-logs
                        Stream the trace for the apply_production job.
  --reader-accounts     Print only the reader_accounts Terraform output from the
                        apply_production job trace.
  --id-only             Print only the resolved pipeline ID.
  -h, --help            Show this help text.
EOF
}

require_glab() {
  if ! command -v glab >/dev/null 2>&1; then
    printf 'glab is required. Install it and authenticate with: glab auth login\n' >&2
    exit 1
  fi
}

extract_reader_accounts() {
  # Terraform renders this value as an HCL-style nested map in the job trace.
  # Keep the complete balanced block rather than attempting to reinterpret it.
  sed -E $'s/\033\\[[0-9;]*[[:alpha:]]//g' | awk '
    function brace_count(line, character, copy) {
      copy = line
      return gsub(character, "", copy)
    }

    /(^|[[:space:]])(reader_accounts|\["reader_accounts"\])[[:space:]]*=/ {
      if (!capturing) {
        capturing = 1
        found = 1
      }
    }

    capturing {
      print
      depth += brace_count($0, "\\{") - brace_count($0, "\\}")
      if (depth == 0 && $0 ~ /\}/) {
        completed = 1
        exit
      }
    }

    END {
      if (!found) {
        print "reader_accounts output was not found in the apply_production trace." > "/dev/stderr"
        exit 1
      }
      if (!completed) {
        print "reader_accounts output ended before its closing brace." > "/dev/stderr"
        exit 1
      }
    }
  '
}

while (($#)); do
  case "$1" in
    --ref)
      ref="${2:?--ref requires a value}"
      shift 2
      ;;
    --repo)
      repo="${2:?--repo requires a value}"
      shift 2
      ;;
    --pipeline-id)
      pipeline_id="${2:?--pipeline-id requires a value}"
      shift 2
      ;;
    --trace)
      trace_job="${2:?--trace requires a job name or ID}"
      shift 2
      ;;
    --apply-production-logs)
      trace_job='apply_production'
      shift
      ;;
    --reader-accounts)
      trace_job='apply_production'
      reader_accounts_only=true
      shift
      ;;
    --id-only)
      id_only=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown option: %s\n\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

require_glab

if [[ -z "$pipeline_id" ]]; then
  pipeline_id="$(
    glab ci list -R "$repo" --ref "$ref" --per-page 1 --output json \
      | sed -nE 's/.*"id"[[:space:]]*:[[:space:]]*([0-9]+).*/\1/p' \
      | head -n 1
  )"

  if [[ -z "$pipeline_id" ]]; then
    printf 'No pipelines found for ref %q in %q.\n' "$ref" "$repo" >&2
    exit 1
  fi
fi

if "$id_only"; then
  printf '%s\n' "$pipeline_id"
  exit 0
fi

if ! "$reader_accounts_only"; then
  printf 'Repository: %s\nRef: %s\nPipeline ID: %s\n\n' "$repo" "$ref" "$pipeline_id"
fi

if [[ -n "$trace_job" ]]; then
  if "$reader_accounts_only"; then
    glab ci trace -R "$repo" --pipeline-id "$pipeline_id" "$trace_job" | extract_reader_accounts
    exit ${PIPESTATUS[0]}
  fi

  exec glab ci trace -R "$repo" --pipeline-id "$pipeline_id" "$trace_job"
fi

exec glab ci get -R "$repo" --pipeline-id "$pipeline_id" --with-job-details
