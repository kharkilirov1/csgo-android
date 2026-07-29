#!/usr/bin/env python3
"""Import a CS:GO 2018 donor into the portable Source Engine tree.

Portable files win by default. CS:GO-owned paths are replaced from the donor.
The operation is deterministic and records every copied file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path


CSGO_OWNED_PREFIXES = (
    "game/client/cstrike15/",
    "game/client/econ/",
    "game/server/cstrike15/",
    "game/server/econ/",
    "game/shared/cstrike15/",
    "game/shared/econ/",
    "gcsdk/",
    "matchmaking/cstrike15/",
    "public/gcsdk/",
)
CSGO_OWNED_FILES = {
    "game/client/client_cstrike15.vpc",
    "game/server/server_cstrike15.vpc",
}
SKIP_PARTS = {".git", "__pycache__"}
RUNTIME_ROOTS = (
    "appframework", "bitmap", "bonesetup", "choreoobjects", "common",
    "datacache", "datamodel", "dedicated", "dedicated_main", "dmserializers",
    "dmxloader", "engine", "engine_ds", "external", "filesystem", "fow",
    "game", "gcsdk", "inputsystem", "interfaces", "launcher", "launcher_main",
    "localize", "matchmaking", "materialobjects", "materialsystem", "mathlib",
    "mdllib", "meshutils", "movieobjects", "particles", "public",
    "resourcefile", "responserules", "scaleformui", "scenefilecache",
    "serverbrowser", "soundemittersystem", "soundsystem", "studiorender",
    "thirdparty", "tier0", "tier1", "tier2", "tier3", "togl", "vgui2", "vguimatsurface",
    "videocfg", "vpklib", "vscript", "vstdlib", "vtf",
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def is_csgo_owned(relative: str) -> bool:
    return relative in CSGO_OWNED_FILES or relative.startswith(CSGO_OWNED_PREFIXES)


def donor_files(donor: Path):
    for root_name in RUNTIME_ROOTS:
        root = donor / root_name
        if not root.is_dir():
            continue
        for directory, names, files in os.walk(root):
            names[:] = sorted(name for name in names if name not in SKIP_PARTS)
            for name in sorted(files):
                yield Path(directory) / name


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--donor", required=True, type=Path)
    parser.add_argument("--target", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("docs/csgo_donor_import_manifest.json"),
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--donor-wins-runtime",
        action="store_true",
        help="replace all overlapping runtime files; use for a coherent CS:GO engine base",
    )
    args = parser.parse_args()

    donor = args.donor.resolve()
    target = args.target.resolve()
    if not (donor / "game/client/cstrike15").is_dir():
        parser.error(f"invalid CS:GO donor: {donor}")
    if not (target / "wscript").is_file():
        parser.error(f"invalid portable Source target: {target}")

    copied: list[dict[str, object]] = []
    skipped_existing = 0
    unchanged = 0
    for source in donor_files(donor):
        relative_path = source.relative_to(donor)
        if any(part in SKIP_PARTS for part in relative_path.parts):
            continue
        relative = relative_path.as_posix()
        destination = target / relative_path
        owned = (
            args.donor_wins_runtime
            and relative_path.parts[0].lower() != "thirdparty"
        ) or is_csgo_owned(relative)
        if destination.exists():
            if not owned:
                skipped_existing += 1
                continue
            if digest(source) == digest(destination):
                unchanged += 1
                continue
        action = "replace-csgo" if destination.exists() else "add"
        copied.append(
            {
                "path": relative,
                "action": action,
                "bytes": source.stat().st_size,
                "sha256": digest(source),
            }
        )
        if not args.dry_run:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

    manifest = {
        "schema": 1,
        "donor": str(donor),
        "target": str(target),
        "dry_run": args.dry_run,
        "donor_wins_runtime": args.donor_wins_runtime,
        "copied_files": len(copied),
        "copied_bytes": sum(int(item["bytes"]) for item in copied),
        "skipped_existing_portable_files": skipped_existing,
        "unchanged_files": unchanged,
        "files": copied,
    }
    manifest_path = args.manifest
    if not manifest_path.is_absolute():
        manifest_path = target / manifest_path
    if not args.dry_run:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    print(json.dumps({key: value for key, value in manifest.items() if key != "files"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
