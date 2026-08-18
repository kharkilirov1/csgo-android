#!/usr/bin/env python3
"""Reject temporary Android UI/VGUI runtime probes."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
FILES = (
    "vgui2/src/InputWin32.cpp",
    "vgui2/src/VPanel.cpp",
    "vgui2/vgui_surfacelib/fonttexturecache.cpp",
    "vguimatsurface/MatSystemSurface.cpp",
    "vguimatsurface/TextureDictionary.cpp",
    "materialsystem/stdshaders/vertexlitgeneric_dx9_helper.cpp",
)
FORBIDDEN = (
    "InputDBG",
    "DBG: GlyphAlpha",
    "DBG: FontKV",
    "DBG: FontMat",
    "DBG: FontPage",
    "DBG: FontShader",
    "DBG: StartDrawing",
    "DBG: MatBad",
    "DBG: DrawQuadArray",
    "DBG: VGUI SetMaterial",
)


def main() -> int:
    matches = []
    for relative in FILES:
        for line_number, line in enumerate(
            (ROOT / relative).read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            if any(marker in line for marker in FORBIDDEN):
                matches.append(f"{relative}:{line_number}: {line.strip()}")

    if matches:
        print("FAIL: temporary UI/VGUI Android probes remain")
        print("\n".join(matches))
        return 1

    print("PASS: no temporary UI/VGUI Android probes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
