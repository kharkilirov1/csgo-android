#!/usr/bin/env python3
"""Convert a text asset to the C byte array expected by Source VScript."""

from __future__ import annotations

import argparse
from pathlib import Path


def render(data: bytes, symbol: str) -> str:
    values = list(data) + [0]
    rows = [
        ", ".join(f"0x{value:02x}" for value in values[offset : offset + 16])
        for offset in range(0, len(values), 16)
    ]
    body = ",\n    ".join(rows)
    return (
        "#pragma once\n\n"
        f"static const char {symbol}[] = {{\n"
        f"    {body}\n"
        "};\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("symbol")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    content = render(args.input.read_bytes(), args.symbol)
    args.output.write_text(content, encoding="ascii", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
