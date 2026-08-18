#!/usr/bin/env python3
"""Reject temporary diagnostics from Android runtime hot paths."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_BY_FILE = {
    "materialsystem/shaderapidx9/shaderapidx8.cpp": (
        "DBG: DrawMeshInternal",
        "__android_log_print",
    ),
    "materialsystem/shaderapidx9/meshdx8.cpp": (
        "DBG: DrawInternal",
        "DBG: DynDrawInternal",
        "__android_log_print",
    ),
    "particles/particles.cpp": (
        "CSHEET_ABI_OK",
        "s_bLoggedSheetABI",
    ),
}


def main() -> int:
    matches = []
    for relative, markers in FORBIDDEN_BY_FILE.items():
        path = ROOT / relative
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_number, line in enumerate(text.splitlines(), 1):
            for marker in markers:
                if marker in line:
                    matches.append(f"{relative}:{line_number}: {marker}")

    if matches:
        print("FAIL: temporary Android runtime probes remain")
        print("\n".join(matches))
        return 1

    print("PASS: no temporary Android runtime probes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
