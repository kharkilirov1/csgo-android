#!/usr/bin/env python3
"""Guard CSheet's Waf implementation/header ABI ownership."""

from pathlib import Path
import runpy
import sys
import types
import re


ROOT = Path(__file__).resolve().parents[1]
PARTICLES_WSCRIPT = ROOT / "particles" / "wscript"
BITMAP_WSCRIPT = ROOT / "bitmap" / "wscript"
PARTICLES_SOURCE = ROOT / "particles" / "particles.cpp"
BITMAP_IMPLEMENTATION = ROOT / "bitmap" / "psheet.cpp"
SERVER_WSCRIPT = ROOT / "game" / "server" / "wscript"
CANONICAL_INCLUDE = '#include "bitmap/psheet.h"'


class BuildRecorder:
    def __init__(self) -> None:
        self.env = types.SimpleNamespace(
            DEST_OS="linux",
            PREFIX=None,
            MSVC_SUBSYSTEM=None,
        )
        self.library = None

    def get_taskgen_count(self) -> int:
        return 0

    def stlib(self, **library: object) -> None:
        self.library = library


def configured_sources(path: Path) -> list[str]:
    fake_waflib = types.ModuleType("waflib")
    fake_waflib.Utils = types.SimpleNamespace()
    previous_waflib = sys.modules.get("waflib")
    sys.modules["waflib"] = fake_waflib
    try:
        namespace = runpy.run_path(str(path))
    finally:
        if previous_waflib is None:
            del sys.modules["waflib"]
        else:
            sys.modules["waflib"] = previous_waflib

    recorder = BuildRecorder()
    namespace["build"](recorder)
    if recorder.library is None:
        raise AssertionError(f"{path} did not configure a static library")
    return list(recorder.library["source"])


def main() -> int:
    particle_sources = configured_sources(PARTICLES_WSCRIPT)
    bitmap_sources = configured_sources(BITMAP_WSCRIPT)
    failures = []

    if CANONICAL_INCLUDE not in PARTICLES_SOURCE.read_text(encoding="utf-8"):
        failures.append("particles.cpp does not consume the canonical bitmap/psheet.h ABI")
    if CANONICAL_INCLUDE not in BITMAP_IMPLEMENTATION.read_text(encoding="utf-8"):
        failures.append("bitmap/psheet.cpp does not implement the canonical bitmap/psheet.h ABI")
    if particle_sources.count("psheet.cpp") != 0:
        failures.append("particles/wscript compiles the incompatible local particles/psheet.cpp")
    if bitmap_sources.count("psheet.cpp") != 1:
        failures.append(
            "bitmap/wscript must compile canonical bitmap/psheet.cpp exactly once "
            f"(found {bitmap_sources.count('psheet.cpp')})"
        )

    server_wscript = SERVER_WSCRIPT.read_text(encoding="utf-8")
    libs_match = re.search(r"^\s*libs\s*=\s*\[(?P<libs>[^]]*)\]", server_wscript, re.MULTILINE)
    if libs_match is None:
        failures.append("game/server/wscript does not expose its static-library link list")
    else:
        server_libraries = re.findall(r"['\"]([^'\"]+)['\"]", libs_match.group("libs"))
        if "particles" not in server_libraries or "bitmap" not in server_libraries:
            failures.append("game/server/wscript must link both particles and bitmap")
        elif server_libraries.index("bitmap") < server_libraries.index("particles"):
            failures.append("game/server/wscript must link bitmap after particles")

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1

    print("PASS: CSheet is compiled once from bitmap/psheet.cpp against bitmap/psheet.h")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
