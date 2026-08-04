---
name: setup
description: Set up the PL data-engineering workspace by adding the repositories documented in README.md as Git submodules and creating a worktree for each. Use when a user asks to initialize this workspace, clone its dependent repositories, add the data repositories as submodules, create their worktrees, or runs /setup.
---

# Workspace Setup

Run the deterministic setup script from this repository's root:

```bash
bash .codex/skills/setup/scripts/setup.sh
```

The script initializes this directory as an independent Git repository if needed, adds the five documented SSH repositories under `repositories/`, and creates a worktree for each under `worktrees/`.

It creates branches named `setup/<repository>` and leaves `.gitmodules` plus the submodule gitlinks staged for review. It does not commit them. Re-running it is safe for configured submodules and registered worktrees.

Use `--dry-run` to show the operations without changing Git state:

```bash
bash .codex/skills/setup/scripts/setup.sh --dry-run
```

Stop and report an error if the script detects tracked or staged changes, an unexpected existing submodule path, or an unregistered worktree directory. Do not remove or overwrite those paths.
