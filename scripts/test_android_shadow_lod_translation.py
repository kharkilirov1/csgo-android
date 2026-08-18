#!/usr/bin/env python3
"""Regression checks for scalar shadow textureLod results on GLSL ES."""

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "togles" / "linuxwin" / "dx9asmtogl2.cpp"


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


text = SOURCE.read_text(encoding="utf-8", errors="replace")
start = text.find("void D3DToGL::Handle_TEX")
end = text.find("void D3DToGL::Handle_TexLDD", start)
if start < 0 or end < 0:
    fail("could not isolate D3DToGL::Handle_TEX")

body = text[start:end]
lod_start = body.find("if ( bIsTexLDL )")
lod_end = body.find("else if ( bIsShadowSampler )", lod_start)
if lod_start < 0 or lod_end < 0:
    fail("could not isolate the TEXLDL branch")

lod_branch = body[lod_start:lod_end]
if "bIsShadowSampler" not in lod_branch:
    fail("TEXLDL does not distinguish sampler2DShadow from sampler2D")
if not re.search(
    r"if\s*\(\s*bIsShadowSampler\s*\).*?vec4\s*\(\s*textureLod\s*\(",
    lod_branch,
    re.DOTALL,
):
    fail("sampler2DShadow textureLod scalar is not replicated into the vec4 D3D destination")
if not re.search(r"else.*?=\s*textureLod\s*\(", lod_branch, re.DOTALL):
    fail("ordinary sampler2D TEXLDL no longer emits the vector textureLod overload")

print("PASS: shadow TEXLDL scalar results are replicated into vec4 destinations")
