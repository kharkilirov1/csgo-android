#!/usr/bin/env python3
"""Guard Android Waf ownership of required datacache app systems."""

from pathlib import Path
import runpy
import sys
import types


ROOT = Path(__file__).resolve().parents[1]
WSCRIPT = ROOT / "datacache" / "wscript"
VPC = ROOT / "datacache" / "datacache.vpc"
REQUIRED = ("resourceaccesscontrol.cpp", "precachesystem.cpp")


class BuildRecorder:
    def __init__(self) -> None:
        self.env = types.SimpleNamespace(
            DEST_OS="linux",
            LIBDIR=None,
            MSVC_SUBSYSTEM=None,
        )
        self.library = None

    def get_taskgen_count(self) -> int:
        return 0

    def shlib(self, **library: object) -> None:
        self.library = library


def configured_sources() -> list[str]:
    fake_waflib = types.ModuleType("waflib")
    fake_waflib.Utils = types.SimpleNamespace()
    previous = sys.modules.get("waflib")
    sys.modules["waflib"] = fake_waflib
    try:
        namespace = runpy.run_path(str(WSCRIPT))
    finally:
        if previous is None:
            del sys.modules["waflib"]
        else:
            sys.modules["waflib"] = previous

    recorder = BuildRecorder()
    namespace["build"](recorder)
    if recorder.library is None:
        raise AssertionError("datacache/wscript did not configure a shared library")
    return list(recorder.library["source"])


def main() -> int:
    sources = configured_sources()
    vpc = VPC.read_text(encoding="utf-8", errors="replace")
    failures = []
    for source in REQUIRED:
        if f'"{source}"' not in vpc:
            failures.append(f"canonical datacache.vpc does not own {source}")
        if sources.count(source) != 1:
            failures.append(
                f"datacache/wscript must compile {source} exactly once "
                f"(found {sources.count(source)})"
            )

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1

    print("PASS: Waf builds both datacache resource-control app systems")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
