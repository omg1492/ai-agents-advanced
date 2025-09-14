"""Run all data import scripts (import_*.py) in a controlled order.

Purpose:
  Discover Python files in this directory whose names start with `import_` and
  execute them one by one, providing a concise progress + result summary.

Default execution order accounts for known soft dependencies (graph taxonomy
depends on base graph, etc.). Any additional matching scripts not in the
predefined list are appended in alphabetical order.

Usage examples (run from repo root or any path):
  uv run python data/scripts/import_all.py              # run all
  uv run python data/scripts/import_all.py --dry-run    # just list
  uv run python data/scripts/import_all.py --only products qna
  uv run python data/scripts/import_all.py --stop-on-error

CLI flags:
  --dry-run          List the resolved script order without executing.
  --only NAMES ...   Subset of base names (without .py) to run, in the order
                     they appear in the master order definition.
  --exclude NAMES ...Exclude specific base names.
  --pattern GLOB     Override file discovery pattern (default: import_*.py).
  --stop-on-error    Abort on first failing script (non‑zero exit code).
  --list             List discovered scripts (ignores other flags that run).

Exit code is 0 only if all executed scripts return 0.

Notes:
  - Scripts are executed in separate subprocesses (isolation, clear logging).
  - This script does not attempt parallel execution to keep logs readable.
  - Incomplete / placeholder scripts will simply surface as failures.
  - Environment variables (.env) are loaded once here; individual scripts may
    also load .env again – harmless duplication.
"""
from __future__ import annotations

import argparse
import fnmatch
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv


# Predefined preferred order (base name without .py). Missing entries are ignored.
PREFERRED_ORDER: list[str] = [
    # Vector / tabular foundations
    "import_concept_embeddings",
    "import_products",
    "import_simple_products",
    "import_qna",
    "import_stock",
    # Graph layer (taxonomy requires base graph)
    "import_graph_age",
    "import_taxonomy_age",
]


@dataclass
class ScriptResult:
    name: str
    path: Path
    return_code: int | None = None
    skipped: bool = False

    @property
    def status(self) -> str:
        if self.skipped:
            return "SKIPPED"
        if self.return_code is None:
            return "PENDING"
        return "OK" if self.return_code == 0 else f"FAIL({self.return_code})"


def discover_scripts(directory: Path, pattern: str) -> list[Path]:
    """Return absolute paths of scripts matching pattern (non-recursive).

    Excludes this orchestrator itself.
    """
    scripts: list[Path] = []
    for entry in directory.iterdir():
        if not entry.is_file():
            continue
        if entry.name == "import_all.py":  # avoid self
            continue
        if fnmatch.fnmatch(entry.name, pattern):
            scripts.append(entry)
    return scripts


def order_scripts(found: list[Path]) -> list[Path]:
    """Apply preferred ordering; append remaining alphabetically."""
    by_name = {p.stem: p for p in found}
    ordered: list[Path] = []
    used = set()
    for name in PREFERRED_ORDER:
        p = by_name.get(name)
        if p:
            ordered.append(p)
            used.add(name)
    # Append any not-yet-used scripts in alphabetical order of stem
    for name in sorted(n for n in by_name.keys() if n not in used):
        ordered.append(by_name[name])
    return ordered


def filter_scripts(paths: list[Path], only: set[str] | None, exclude: set[str]) -> list[Path]:
    """Filter by --only / --exclude sets (use stem names)."""
    result: list[Path] = []
    for p in paths:
        stem = p.stem
        if only is not None and stem not in only:
            continue
        if stem in exclude:
            continue
        result.append(p)
    return result


def run_script(script: Path) -> int:
    """Execute a script in a subprocess and return its exit code."""
    cmd = [sys.executable, str(script)]
    # Stream output directly; user can see progress.
    return subprocess.call(cmd)


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run all import_*.py data scripts.")
    parser.add_argument("--pattern", default="import_*.py", help="Glob for discovery (default: import_*.py)")
    parser.add_argument("--dry-run", action="store_true", help="Show execution order then exit")
    parser.add_argument("--only", nargs="*", help="Subset of base names (no .py) to run in resolved order")
    parser.add_argument("--exclude", nargs="*", default=[], help="Base names to exclude")
    parser.add_argument("--stop-on-error", action="store_true", help="Abort on first failure")
    parser.add_argument("--list", action="store_true", help="List discovered scripts (unsorted) and exit")
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] | None = None) -> int:
    load_dotenv()  # Load once (scripts may load again; that's fine)
    args = parse_args(argv or sys.argv[1:])
    base_dir = Path(__file__).parent
    discovered = discover_scripts(base_dir, args.pattern)

    if args.list:
        for p in sorted(discovered):
            print(p.name)
        return 0

    ordered = order_scripts(discovered)
    only_set = set(args.only) if args.only else None
    exclude_set = set(args.exclude)
    final_scripts = filter_scripts(ordered, only_set, exclude_set)

    if not final_scripts:
        print("No scripts selected.")
        return 0

    if args.dry_run:
        print("Execution order:")
        for p in final_scripts:
            print(f"  {p.name}")
        return 0

    results: list[ScriptResult] = [ScriptResult(name=p.stem, path=p) for p in final_scripts]
    overall_ok = True
    print(f"Running {len(results)} import scripts...\n")
    for res in results:
        print(f"==> {res.name}...")
        code = run_script(res.path)
        res.return_code = code
        if code != 0:
            overall_ok = False
            print(f"   {res.name} FAILED (exit {code})")
            if args.stop_on_error:
                print("Stopping due to --stop-on-error.")
                break
        else:
            print(f"   {res.name} OK")
        print()

    # Summary table
    print("Summary:\n--------")
    width = max(len(r.name) for r in results)
    for r in results:
        print(f"{r.name.ljust(width)}  {r.status}")
    print()
    if overall_ok:
        print("All selected scripts completed successfully.")
        return 0
    print("One or more scripts failed.")
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
