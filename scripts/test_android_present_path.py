#!/usr/bin/env python3
"""Regression check for the Android texture-to-window presentation path."""

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
GLMGR = ROOT / "togles/linuxwin/glmgr.cpp"


def fail(message: str) -> int:
    print(f"FAIL: {message}")
    return 1


def main() -> int:
    source = GLMGR.read_text(encoding="utf-8")
    match = re.search(
        r"void\s+GLMContext::Present\s*\([^)]*\)\s*\{(?P<body>.*?)\n\}",
        source,
        re.DOTALL,
    )
    if not match:
        return fail("could not locate GLMContext::Present")

    body = match.group("body")
    start = body.find("if (newRefreshMode)")
    end = body.find("showparams.m_noBlit = true;", start)
    if start < 0 or end < 0:
        return fail("could not locate the new-refresh presentation block")

    present_block = body[start:end]
    if "Present blit SKIPPED (android)" in present_block:
        return fail("Android explicitly skips the texture-to-default-framebuffer blit")

    if not re.search(r"\bBlit2\s*\(", present_block):
        return fail("new-refresh path marks noBlit without first calling Blit2")

    android_gated_blit = re.search(
        r"#ifdef\s+__ANDROID__.*?#else\s*.*?\bBlit2\s*\(.*?#endif",
        present_block,
        re.DOTALL,
    )
    if android_gated_blit:
        return fail("Blit2 is compiled only for non-Android targets")

    print("PASS: Android new-refresh path blits to the default framebuffer before swap")
    return 0


if __name__ == "__main__":
    sys.exit(main())
