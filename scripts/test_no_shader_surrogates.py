#!/usr/bin/env python3
"""Reject Android-only shaders that hide missing/corrupt VCS assets."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SHADER_MANAGER = ROOT / "materialsystem/shaderapidx9/vertexshaderdx8.cpp"
TOGLES_DEVICE = ROOT / "togles/linuxwin/dxabstract.cpp"


def require_absent(text: str, needle: str, description: str) -> None:
    if needle in text:
        raise AssertionError(f"{description}: found {needle!r}")


def main() -> None:
    manager = SHADER_MANAGER.read_text(encoding="utf-8", errors="replace")
    device = TOGLES_DEVICE.read_text(encoding="utf-8", errors="replace")

    manager_forbidden = {
        "CreateD3DVertexShader( NULL": "NULL-bytecode vertex shader surrogate",
        "CreateD3DPixelShader( NULL": "NULL-bytecode pixel shader surrogate",
        "m_Flags &= ~SHADER_FAILED_LOAD": "clearing a real shader-load failure",
        "fallback_ps_inline": "late inline pixel-shader surrogate",
        "fallback arrays are 32 slots": "hard-coded fake combo table",
    }
    for needle, description in manager_forbidden.items():
        require_absent(manager, needle, description)

    device_forbidden = {
        "vec4( 1.0, 0.0, 0.0, 1.0 )": "solid-red diagnostic fragment shader",
        "v0.x / 1170.0": "hard-coded fallback width",
        "v0.y / 540.0": "hard-coded fallback height",
        "no .vcs bytecode available": "silent missing-VCS fallback path",
    }
    for needle, description in device_forbidden.items():
        require_absent(device, needle, description)

    print("PASS: missing VCS assets cannot be hidden by Android shader surrogates")


if __name__ == "__main__":
    main()
