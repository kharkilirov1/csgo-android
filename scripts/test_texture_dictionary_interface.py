#!/usr/bin/env python3
"""Keep every VGUI texture-dictionary caller on one canonical vtable ABI."""

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
FORWARD_HEADER = ROOT / "vguimatsurface" / "TextureDictionary.h"
SURFACELIB_FORWARD_HEADER = ROOT / "vgui2" / "vgui_surfacelib" / "texturedictionary.h"
CANONICAL_HEADER = ROOT / "common" / "vgui_surfacelib" / "texturedictionary.h"
SOURCE = ROOT / "vguimatsurface" / "TextureDictionary.cpp"


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


header = FORWARD_HEADER.read_text(encoding="utf-8", errors="replace")
surfacelib_header = SURFACELIB_FORWARD_HEADER.read_text(encoding="utf-8", errors="replace")
source = SOURCE.read_text(encoding="utf-8", errors="replace")

if '#include "vgui_surfacelib/texturedictionary.h"' not in header:
    fail("vguimatsurface still declares a second ITextureDictionary ABI")
if re.search(r"class\s+ITextureDictionary\b", header):
    fail("forwarding header must not redeclare ITextureDictionary")
if '#include "../../common/vgui_surfacelib/texturedictionary.h"' not in surfacelib_header:
    fail("vgui_surfacelib does not forward to the canonical texture dictionary ABI")
if re.search(r"class\s+ITextureDictionary\b", surfacelib_header):
    fail("vgui_surfacelib forwarding header redeclares ITextureDictionary")

definitions = 0
for path in (CANONICAL_HEADER, FORWARD_HEADER, SURFACELIB_FORWARD_HEADER):
    definitions += len(re.findall(r"class\s+ITextureDictionary\b", path.read_text(encoding="utf-8", errors="replace")))
if definitions != 1:
    fail(f"expected one ITextureDictionary definition, found {definitions}")

class_start = source.find("class CTextureDictionary : public ITextureDictionary")
class_end = source.find("static CTextureDictionary s_TextureDictionary", class_start)
if class_start < 0 or class_end < 0:
    fail("could not isolate CTextureDictionary")
class_body = source[class_start:class_end]

if "CreateTextureByTexture" in source:
    fail("obsolete virtual CreateTextureByTexture shifts every subsequent vtable slot")
if not re.search(r"HRenderTexture\s+GetTextureHandle\s*\(\s*int\s+textureId\s*\)", class_body):
    fail("canonical Source2 GetTextureHandle slot is missing")
if not re.search(
    r"SetTextureRGBAEx\s*\([^;]*ImageFormat\s+format\s*,\s*ETextureScaling\s+eScaling\s*\)",
    class_body,
):
    fail("SetTextureRGBAEx does not use the canonical ETextureScaling signature")
for method in (
    "BindTextureToMaterial2Reference",
    "BindTextureToMaterial2",
    "GetTextureMaterial2",
):
    if method not in class_body:
        fail(f"canonical tail slot {method} is missing")

if "bool bFixupTextCoordsForDimensions" in source:
    fail("legacy SetTextureRGBAEx bool ABI remains in the implementation")

print("PASS: vguimatsurface implements the canonical VGUI texture-dictionary ABI")
