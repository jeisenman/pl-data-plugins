#!/usr/bin/env python3
"""Find added DTO fields in a git diff and search a pipelines repository for them."""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

DEFAULT_GLOBS = ("*Dto*", "*DTO*", "*Contract*", "*Request*", "*Response*")
SOURCE_SUFFIXES = {".cs", ".java", ".kt", ".ts", ".tsx"}
FIELD = re.compile(
    r"^\+\s*(?:public|private|protected|internal|readonly|static|final|val|var|export)?\s*"
    r"(?:[A-Za-z_][\w<>?,.\[\]| ]*\s+)?([a-zA-Z_][\w]*)\s*(?:[;={]|:\s*[^;=,{]+[;=,{])"
)
SKIP = {"class", "interface", "record", "enum", "return", "get", "set", "constructor"}


@dataclass
class Candidate:
    file: str
    dto: str
    field: str
    declaration: str
    normalized: str
    pipeline_matches: list[str]
    status: str


def run(*args: str, cwd: Path) -> str:
    return subprocess.run(args, cwd=cwd, check=True, text=True, capture_output=True).stdout


def normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--application", required=True, type=Path)
    parser.add_argument("--pipelines", required=True, type=Path)
    parser.add_argument("--from-ref", required=True)
    parser.add_argument("--to-ref", default="HEAD")
    parser.add_argument("--contract-glob", action="append", dest="globs")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--json-output", type=Path)
    return parser.parse_args()


def is_contract_file(path: str, globs: list[str]) -> bool:
    name = Path(path).name
    return Path(path).suffix.lower() in SOURCE_SUFFIXES and any(fnmatch.fnmatch(name, glob) for glob in globs)


def extract_candidates(diff: str, globs: list[str]) -> list[Candidate]:
    candidates: list[Candidate] = []
    current_file = ""
    current_dto = ""
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:]
            current_dto = ""
            continue
        if line.startswith("@@"):
            # Generated DTO diffs carry the surrounding class or constructor in the hunk context.
            hunk_context = line.rsplit("@@", 1)[-1]
            dto_match = re.search(r"\b([A-Za-z_]\w*(?:DTO|Dto|Contract|Request|Response))\s*(?:\(|:|$)", hunk_context)
            if dto_match:
                current_dto = dto_match.group(1)
            continue
        if not current_file or not is_contract_file(current_file, globs) or not line.startswith("+") or line.startswith("+++"):
            continue
        # Assignments in generated copy constructors are not field declarations.
        if "=" in line:
            continue
        match = FIELD.match(line)
        if not match:
            continue
        field = match.group(1)
        if field.lower() in SKIP or field[0].islower() and "(" in line:
            continue
        candidates.append(Candidate(current_file, current_dto or Path(current_file).stem, field, line[1:].strip(), normalize(field), [], "candidate gap"))
    return candidates


def find_matches(pipelines: Path, candidate: Candidate) -> list[str]:
    # Search the original and a tokenized spelling; paths make manual validation quick.
    tokens = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)|\d+", candidate.field)
    queries = {candidate.field.lower(), "_".join(t.lower() for t in tokens), "-".join(t.lower() for t in tokens)}
    matches: list[str] = []
    for path in pipelines.rglob("*"):
        if not path.is_file() or ".git" in path.parts or path.stat().st_size > 2_000_000:
            continue
        try:
            content = path.read_text(errors="ignore").lower()
        except OSError:
            continue
        if any(query in content for query in queries):
            matches.append(str(path.relative_to(pipelines)))
            if len(matches) == 8:
                break
    return matches


def markdown(args: argparse.Namespace, items: list[Candidate]) -> str:
    lines = [
        "# DTO contract gap report",
        "",
        f"- Application: `{args.application}` (`{args.from_ref}` → `{args.to_ref}`)",
        f"- Pipelines: `{args.pipelines}`",
        "- Limitation: matches are text evidence only; confirm source lineage and semantic equivalence.",
        "",
        "| DTO file and field | Added declaration | Pipeline evidence | Review question |",
        "|---|---|---|---|",
    ]
    for item in items:
        evidence = ", ".join(f"`{m}`" for m in item.pipeline_matches) or "No text match found"
        lines.append(f"| `{item.dto}.{item.field}` | `{item.declaration}` | {evidence} | Would this field be useful to track over time? |")
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    args.application = args.application.resolve()
    args.pipelines = args.pipelines.resolve()
    if not (args.application / ".git").exists() or not (args.pipelines / ".git").exists():
        raise SystemExit("--application and --pipelines must be Git working trees")
    globs = args.globs or list(DEFAULT_GLOBS)
    diff = run("git", "diff", "--unified=0", args.from_ref, args.to_ref, "--", cwd=args.application)
    items = extract_candidates(diff, globs)
    for item in items:
        item.pipeline_matches = find_matches(args.pipelines, item)
        item.status = "represented" if item.pipeline_matches else "candidate gap"
    report = markdown(args, items)
    if args.output:
        args.output.write_text(report)
    else:
        print(report, end="")
    if args.json_output:
        args.json_output.write_text(json.dumps([asdict(item) for item in items], indent=2) + "\n")


if __name__ == "__main__":
    main()
