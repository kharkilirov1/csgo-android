#!/usr/bin/env python3
"""Ensure missing weapon-data failures identify the entity classname."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "game" / "shared" / "cstrike15" / "weapon_csbase.cpp"


def main() -> int:
    text = SOURCE.read_text(encoding="utf-8", errors="replace")
    match = re.search(
        r"if\s*\(\s*GetWeaponFileInfoHandle\(\).*?AssertFatalMsg\s*\(",
        text,
        re.DOTALL,
    )
    if match is None:
        print("FAIL: missing weapon-info fatal guard not found")
        return 1
    guard = match.group(0)
    if "GetClassname()" not in guard:
        print("FAIL: missing weapon-info diagnostic does not report the classname")
        return 1
    if "GetName()" in guard:
        print("FAIL: missing weapon-info diagnostic reads the already-missing weapon-data name")
        return 1
    print("PASS: missing weapon-info fatal diagnostic reports the entity classname")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
