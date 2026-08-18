#!/usr/bin/env python3
"""Reject calls to the removed AndroidSymbolDebug diagnostic hook."""

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SUFFIXES = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx", ".inc", ".inl", ".m", ".mm"}
SYMBOL = "Android" + "SymbolDebug"


def main() -> int:
    matches = []
    pathspecs = [f"*{suffix}" for suffix in sorted(SOURCE_SUFFIXES)]
    tracked = subprocess.run(
        ["git", "grep", "-n", "-F", SYMBOL, "--", *pathspecs],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if tracked.returncode not in (0, 1):
        print(tracked.stderr.strip() or "FAIL: git grep failed")
        return 1
    if tracked.stdout:
        matches.extend(tracked.stdout.splitlines())

    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    ).stdout.split(b"\0")
    for raw_path in untracked:
        if not raw_path:
            continue
        relative_path = Path(raw_path.decode("utf-8", errors="surrogateescape"))
        if relative_path.suffix.lower() not in SOURCE_SUFFIXES:
            continue
        path = ROOT / relative_path
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_number, line in enumerate(text.splitlines(), 1):
            if SYMBOL in line:
                matches.append(f"{relative_path}:{line_number}: {line.strip()}")

    if matches:
        print("FAIL: removed Android diagnostic hook is still referenced")
        for match in matches:
            print(match)
        return 1

    print("PASS: no source references the removed AndroidSymbolDebug hook")
    return 0


if __name__ == "__main__":
    sys.exit(main())
