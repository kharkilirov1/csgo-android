#!/usr/bin/env python3
"""Regression guard for Android CUtlSymbolTable pointer semantics."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tier1" / "utlsymbol.cpp"


def section(text: str, start: str, end: str) -> str:
    begin = text.index(start)
    finish = text.index(end, begin)
    return text[begin:finish]


def main() -> int:
    text = SOURCE.read_text(encoding="utf-8", errors="replace")
    comparator = section(
        text,
        "bool CUtlSymbolTable::CLess::operator()",
        "CUtlSymbolTable::CUtlSymbolTable",
    )
    pool_lookup = section(
        text,
        "int CUtlSymbolTable::FindPoolWithSpace",
        "CUtlSymbol CUtlSymbolTable::AddString",
    )
    add_string = section(
        text,
        "CUtlSymbol CUtlSymbolTable::AddString",
        "const char* CUtlSymbolTable::String",
    )

    failures = []
    for name, body in (
        ("symbol comparator", comparator),
        ("pool lookup", pool_lookup),
        ("AddString", add_string),
    ):
        if "#ifdef ANDROID" in body or "uintptr_t" in body:
            failures.append(f"{name} contains Android address heuristics")

    if "RemoveAll" in comparator:
        failures.append("symbol comparator mutates its owning table")

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1

    print("PASS: Android uses canonical CUtlSymbolTable lookup semantics")
    return 0


if __name__ == "__main__":
    sys.exit(main())
