#!/usr/bin/env python3
"""Inventory a CS:GO donor tree against this portable Source Engine fork."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path


SOURCE_EXTENSIONS = {".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".inl"}
INCLUDE_RE = re.compile(r'^\s*#\s*include\s*[<"]([^">]+)[">]', re.MULTILINE)
VPC_FILE_RE = re.compile(r'\$File\s+"([^"]+)"', re.IGNORECASE)
SYSTEM_HEADERS = {
    "alloca.h", "assert.h", "ctype.h", "direct.h", "dlfcn.h", "errno.h",
    "fcntl.h", "float.h", "inttypes.h", "io.h", "limits.h", "locale.h",
    "malloc.h", "math.h", "memory.h", "process.h", "pthread.h", "signal.h",
    "stdarg.h", "stddef.h", "stdint.h", "stdio.h", "stdlib.h", "string.h",
    "strings.h", "time.h", "unistd.h", "wchar.h", "windows.h",
}


def relative_files(root: Path) -> set[str]:
    return {
        path.relative_to(root).as_posix().lower()
        for path in root.rglob("*")
        if path.is_file() and ".git" not in path.parts
    }


def code_files(root: Path) -> list[Path]:
    return [
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in SOURCE_EXTENSIONS
    ]


def normalize_vpc_path(raw: str, vpc: Path, donor: Path) -> str | None:
    value = raw.replace("\\", "/")
    if "$" in value or "*" in value:
        if not value.upper().startswith("$SRCDIR/") or "$" in value[len("$SRCDIR/"):]:
            return None
        value = value[len("$SRCDIR/"):]
        candidate = donor / value
    else:
        candidate = vpc.parent / value
    try:
        return candidate.resolve().relative_to(donor).as_posix().lower()
    except ValueError:
        return None


def collect_vpc_references(donor: Path) -> tuple[set[str], set[str]]:
    references: set[str] = set()
    dynamic: set[str] = set()
    for vpc in donor.rglob("*.vpc"):
        text = vpc.read_text(encoding="utf-8", errors="ignore")
        for raw in VPC_FILE_RE.findall(text):
            normalized = normalize_vpc_path(raw, vpc, donor)
            if normalized is None:
                dynamic.add(raw)
            else:
                references.add(normalized)
    return references, dynamic


def collect_gameplay_includes(donor: Path) -> Counter[str]:
    includes: Counter[str] = Counter()
    gameplay_roots = [
        donor / "game/client/cstrike15",
        donor / "game/server/cstrike15",
        donor / "game/shared/cstrike15",
    ]
    for root in gameplay_roots:
        if not root.exists():
            continue
        for path in code_files(root):
            text = path.read_text(encoding="utf-8", errors="ignore")
            includes.update(value.replace("\\", "/").lower() for value in INCLUDE_RE.findall(text))
    return includes


def find_include(include: str, files: set[str]) -> bool:
    if include in SYSTEM_HEADERS:
        return True
    if include in files:
        return True
    suffix = "/" + include
    return any(path.endswith(suffix) for path in files)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--donor", type=Path, required=True)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    args = parser.parse_args()

    source = args.source.resolve()
    donor = args.donor.resolve()
    if not (source / "wscript").is_file():
        parser.error(f"portable source root is invalid: {source}")
    if not (donor / "game/client/cstrike15").is_dir():
        parser.error(f"CS:GO donor root is invalid: {donor}")

    source_files = relative_files(source)
    donor_files = relative_files(donor)
    vpc_refs, dynamic_vpc_refs = collect_vpc_references(donor)
    missing_vpc_refs = sorted(ref for ref in vpc_refs if ref not in donor_files)
    includes = collect_gameplay_includes(donor)
    donor_missing_includes = sorted(
        include for include in includes if not find_include(include, donor_files)
    )
    source_missing_includes = sorted(
        include for include in includes if not find_include(include, source_files)
    )

    modules = {}
    for name in ("client", "server", "shared"):
        root = donor / f"game/{name}/cstrike15"
        modules[name] = len(code_files(root)) if root.exists() else 0

    common = source_files & donor_files
    donor_only = donor_files - source_files
    source_only = source_files - donor_files
    report = {
        "source_root": str(source),
        "donor_root": str(donor),
        "file_inventory": {
            "source": len(source_files),
            "donor": len(donor_files),
            "common_paths": len(common),
            "donor_only_paths": len(donor_only),
            "source_only_paths": len(source_only),
        },
        "csgo_gameplay_code_files": modules,
        "vpc": {
            "literal_file_references": len(vpc_refs),
            "dynamic_file_references": len(dynamic_vpc_refs),
            "missing_literal_references_in_donor": len(missing_vpc_refs),
            "missing_literal_reference_examples": missing_vpc_refs[:100],
        },
        "gameplay_includes": {
            "unique": len(includes),
            "missing_in_donor": len(donor_missing_includes),
            "missing_in_portable_source": len(source_missing_includes),
            "missing_in_portable_source_top": [
                {"include": value, "uses": includes[value]}
                for value in sorted(
                    source_missing_includes, key=lambda item: (-includes[item], item)
                )[:100]
            ],
        },
        "port_gates": [
            "Import cstrike15 gameplay and its generated protobuf headers.",
            "Port CSTRIKE15 engine interfaces before compiling gameplay DLLs.",
            "Disable or replace Scaleform, Steam, GC, economy and matchmaking for the first offline build.",
            "Add csgo VPC lists to the Waf client/server game registries.",
            "Compile server first, then client, then run an Android ARM64 map-load smoke test.",
        ],
    }

    payload = json.dumps(report, indent=2, ensure_ascii=False)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(payload + "\n", encoding="utf-8")

    markdown = f"""# CS:GO 2018 → portable Source Engine audit

## Inputs

- Portable engine: `{source}`
- CS:GO donor: `{donor}`

## Inventory

| Metric | Count |
|---|---:|
| Portable tree files | {len(source_files)} |
| Donor tree files | {len(donor_files)} |
| Same relative paths | {len(common)} |
| Donor-only paths | {len(donor_only)} |
| Portable-only paths | {len(source_only)} |
| CS:GO client code files | {modules['client']} |
| CS:GO server code files | {modules['server']} |
| CS:GO shared code files | {modules['shared']} |

## Build and API gates

- Donor VPC literal `$File` references: **{len(vpc_refs)}**
- Missing literal VPC references inside donor: **{len(missing_vpc_refs)}**
- Unique includes used by CS:GO gameplay: **{len(includes)}**
- Includes not resolvable in donor: **{len(donor_missing_includes)}**
- Includes not resolvable in portable tree: **{len(source_missing_includes)}**

The portable engine cannot compile the donor gameplay by copying only
`game/*/cstrike15`: the missing include count is the measurable compatibility
boundary. See the JSON output for the ranked missing-header list.

## Ordered implementation gates

1. Import gameplay plus generated protobuf headers into an isolated `csgo` path.
2. Port required `CSTRIKE15` engine/public interfaces.
3. Build an offline dedicated server with Steam/GC/economy/UI excluded.
4. Build the client with a minimal VGUI/touch shell instead of Scaleform.
5. Prove Android ARM64 map load, spawn, movement, shooting and round restart.
"""
    if args.markdown_out:
        args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_out.write_text(markdown, encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
