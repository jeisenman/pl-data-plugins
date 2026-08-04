#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
workspace_dir="$(cd "$script_dir/.." && pwd)"
repositories_dir="${REPOSITORIES_DIR:-$workspace_dir/repositories}"
dry_run=false
failures=0

usage() {
  cat <<'EOF'
Usage: scripts/update-worktrees.sh [--dry-run] [--repositories-dir <path>]

Fetch every Git repository below repositories/ and fast-forward each clean branch
worktree from its configured upstream. Dirty, detached, and no-upstream worktrees
are reported and left unchanged.

Options:
  --dry-run                    Report the updates without changing worktrees.
  --repositories-dir <path>    Repository root (default: ./repositories).
  -h, --help                   Show this help message.
EOF
}

log() {
  printf '[%s] %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*"
}

run() {
  if "$dry_run"; then
    log "DRY RUN: $*"
  else
    "$@"
  fi
}

while (($#)); do
  case "$1" in
    --dry-run)
      dry_run=true
      ;;
    --repositories-dir)
      shift
      repositories_dir="${1:?--repositories-dir requires a path}"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown argument: %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

if [[ ! -d "$repositories_dir" ]]; then
  printf 'Repository directory does not exist: %s\n' "$repositories_dir" >&2
  exit 2
fi

while IFS= read -r git_entry; do
  repository="${git_entry%/.git}"
  log "Fetching $(basename "$repository")."

  if ! run git -C "$repository" fetch --all --prune; then
    log "FAILED: fetch for $repository"
    failures=$((failures + 1))
    continue
  fi

  while IFS= read -r worktree; do
    if [[ "$(git -C "$worktree" rev-parse --is-inside-work-tree 2>/dev/null || true)" != "true" ]]; then
      log "SKIP Git metadata path: $worktree"
      continue
    fi

    branch="$(git -C "$worktree" symbolic-ref -q --short HEAD || true)"
    if [[ -z "$branch" ]]; then
      log "SKIP detached HEAD: $worktree"
      continue
    fi

    if [[ -n "$(git -C "$worktree" status --porcelain)" ]]; then
      log "SKIP dirty worktree ($branch): $worktree"
      continue
    fi

    upstream="$(git -C "$worktree" rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null || true)"
    if [[ -z "$upstream" ]]; then
      log "SKIP no upstream ($branch): $worktree"
      continue
    fi

    log "Updating $branch in $worktree from $upstream."
    if ! run git -C "$worktree" merge --ff-only "$upstream"; then
      log "FAILED: update $branch in $worktree; resolve it there before rerunning."
      failures=$((failures + 1))
    fi
  done < <(
    printf '%s\n' "$repository"
    git -C "$repository" worktree list --porcelain | sed -n 's/^worktree //p'
  )
done < <(find "$repositories_dir" -mindepth 2 -maxdepth 2 -name .git -print | sort)

if ((failures)); then
  log "Completed with $failures failure(s)."
  exit 1
fi

log "Completed successfully."
