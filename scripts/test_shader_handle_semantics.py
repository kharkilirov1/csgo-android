#!/usr/bin/env python3
"""Regression check for pointer-backed shader dictionary handles."""

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
SHADER_MANAGER = ROOT / "materialsystem/shaderapidx9/vertexshaderdx8.cpp"
LINKED_LIST = ROOT / "public/tier1/utllinkedlist.h"


def main() -> int:
    shader_source = SHADER_MANAGER.read_text(encoding="utf-8")
    linked_list_source = LINKED_LIST.read_text(encoding="utf-8")

    pointer_backed = re.search(
        r"class\s+CUtlFixedLinkedList\s*:\s*public\s+CUtlLinkedList\s*<"
        r"\s*T\s*,\s*intp\s*,\s*true\s*,\s*intp\s*,\s*CUtlFixedMemory",
        linked_list_source,
        re.MULTILINE,
    )
    if not pointer_backed:
        print("FAIL: could not prove CUtlFixedLinkedList uses intp pointer-backed indices")
        return 1

    numeric_guards = list(
        re.finditer(
            r"(?:shader|vs|ps)\s*<\s*0\s*\|\|\s*"
            r"(?:shader|vs|ps)\s*>=\s*m_(?:Vertex|Pixel)ShaderDict\.Count\(\)",
            shader_source,
        )
    )
    if numeric_guards:
        lines = shader_source.splitlines()
        for match in numeric_guards:
            line_number = shader_source.count("\n", 0, match.start()) + 1
            print(f"FAIL:{line_number}: pointer-backed shader handle compared as a numeric offset")
            print(f"  {lines[line_number - 1].strip()}")
        return 1

    # Pointer-backed handles cannot be range checked safely in release builds:
    # CUtlFixedLinkedList::IsValidIndex dereferences the candidate pointer.
    # Reject only the container's null sentinel. Dynamic combo indices remain
    # ordinary array offsets and must be bounds checked independently.
    for dictionary, getter in (
        ("m_VertexShaderDict", "GetVertexShader"),
        ("m_PixelShaderDict", "GetPixelShader"),
    ):
        match = re.search(
            rf"HardwareShader_t\s+CShaderManager::{getter}\([^{{]+\)\s*\{{(.*?)\n\}}",
            shader_source,
            re.DOTALL,
        )
        if not match:
            print(f"FAIL: could not isolate {getter}")
            return 1
        body = match.group(1)
        shader_type = "VertexShader_t" if getter == "GetVertexShader" else "PixelShader_t"
        if f"({shader_type})INVALID_SHADER" not in body:
            print(f"FAIL: {getter} does not reject the public 0xffffffff INVALID_SHADER value")
            return 1
        if f"{dictionary}.InvalidIndex()" not in body:
            print(f"FAIL: {getter} does not reject the pointer container's null sentinel")
            return 1
        if f"{dictionary}.IsValidIndex" in body:
            print(f"FAIL: {getter} calls unsafe release-mode IsValidIndex on an untrusted pointer")
            return 1
        if "dynIdx < 0" not in body or "dynIdx >=" not in body:
            print(f"FAIL: {getter} does not bounds-check the dynamic combo index")
            return 1

    print("PASS: pointer-backed shader sentinels and dynamic combo offsets are handled separately")
    return 0


if __name__ == "__main__":
    sys.exit(main())
