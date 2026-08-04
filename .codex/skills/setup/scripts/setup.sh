#!/usr/bin/env bash

set -euo pipefail

readonly REPOSITORIES=(
  "di-pipelines|git@github.com:precisionlender/di-pipelines.git"
  "di-pyjobs|git@github.com:precisionlender/di-pyjobs.git"
  "di-scheduling|git@github.com:precisionlender/di-scheduling.git"
  "di-schema-definitions|git@github.com:precisionlender/di-schema-definitions.git"
  "pl-application|git@github.com:precisionlender/pl-application.git"
)

usage() {
  cat <<'EOF'
Usage: setup.sh [--dry-run]

Add the documented repositories as submodules and create one worktree per
submodule at worktrees/<repository> on branch setup/<repository>.
EOF
}

dry_run=false
case "${1:-}" in
  "") ;;
  --dry-run) dry_run=true ;;
  --help|-h)
    usage
    exit 0
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
project_root=$(cd "$script_dir/../../../.." && pwd -P)

run() {
  if "$dry_run"; then
    printf '+ '
    printf '%q ' "$@"
    printf '\n'
    return
  fi
  "$@"
}

if "$dry_run"; then
  printf 'Would create or update the following workspace:\n'
  printf '+ git -C %q init\n' "$project_root"
  for entry in "${REPOSITORIES[@]}"; do
    IFS='|' read -r name url <<< "$entry"
    printf '+ git -C %q submodule add --name %q %q %q\n' "$project_root" "$name" "$url" "repositories/$name"
    printf '+ mkdir -p %q\n' "$project_root/worktrees"
    printf '+ git -C %q worktree add -b %q %q origin/HEAD\n' "$project_root/repositories/$name" "setup/$name" "$project_root/worktrees/$name"
  done
  exit 0
fi

if [[ ! -e "$project_root/.git" ]]; then
  run git -C "$project_root" init
fi

if ! git -C "$project_root" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  printf 'Unable to initialize a Git repository at %s\n' "$project_root" >&2
  exit 1
fi

if ! git -C "$project_root" diff --quiet || ! git -C "$project_root" diff --cached --quiet; then
  printf 'Commit or stash tracked and staged changes before running setup.\n' >&2
  exit 1
fi

run mkdir -p "$project_root/worktrees"

for entry in "${REPOSITORIES[@]}"; do
  IFS='|' read -r name url <<< "$entry"
  submodule_path="repositories/$name"
  submodule_dir="$project_root/$submodule_path"
  worktree_dir="$project_root/worktrees/$name"
  worktree_branch="setup/$name"

  if git -C "$project_root" config -f .gitmodules --get "submodule.$submodule_path.url" >/dev/null 2>&1; then
    run git -C "$project_root" submodule update --init -- "$submodule_path"
  elif [[ -e "$submodule_dir" ]]; then
    printf 'Refusing to replace existing non-submodule path: %s\n' "$submodule_dir" >&2
    exit 1
  else
    run git -C "$project_root" submodule add --name "$name" "$url" "$submodule_path"
  fi

  if [[ -e "$worktree_dir" ]]; then
    if git -C "$submodule_dir" worktree list --porcelain | awk -v path="$worktree_dir" '$1 == "worktree" && $2 == path { found = 1 } END { exit !found }'; then
      printf 'Worktree already exists: %s\n' "$worktree_dir"
      continue
    fi
    printf 'Refusing to replace unregistered worktree path: %s\n' "$worktree_dir" >&2
    exit 1
  fi

  if git -C "$submodule_dir" show-ref --verify --quiet "refs/heads/$worktree_branch"; then
    run git -C "$submodule_dir" worktree add "$worktree_dir" "$worktree_branch"
  else
    default_ref=$(git -C "$submodule_dir" symbolic-ref --quiet --short refs/remotes/origin/HEAD || printf 'HEAD')
    run git -C "$submodule_dir" worktree add -b "$worktree_branch" "$worktree_dir" "$default_ref"
  fi
done

printf '\nSetup complete. Review and commit the staged submodule changes when ready:\n'
git -C "$project_root" status --short
