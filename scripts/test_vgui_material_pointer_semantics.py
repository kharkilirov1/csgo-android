#!/usr/bin/env python3
"""Prevent address-range guesses from hiding VGUI ABI bugs."""

from pathlib import Path
import sys


SOURCE = Path(__file__).resolve().parents[1] / "vguimatsurface" / "TextureDictionary.cpp"
text = SOURCE.read_text(encoding="utf-8", errors="replace")


def isolate(start_marker: str, end_marker: str) -> str:
    start = text.find(start_marker)
    end = text.find(end_marker, start + len(start_marker))
    if start < 0 or end < 0:
        print(f"FAIL: could not isolate {start_marker}", file=sys.stderr)
        raise SystemExit(1)
    return text[start:end]


set_material = isolate(
    "void CMatSystemTexture::SetMaterial",
    "void CMatSystemTexture::ReferenceOtherProcedural",
)
reference = isolate(
    "void CMatSystemTexture::ReferenceOtherProcedural",
    "void CMatSystemTexture::SetMaterial( const char *pFileName )",
)

for name, body in (("SetMaterial", set_material), ("ReferenceOtherProcedural", reference)):
    if "0x700000000000" in body or "0xB00000000000" in body or "0xC0000000000000" in body:
        print(f"FAIL: {name} rejects materials by guessed platform-specific address ranges", file=sys.stderr)
        raise SystemExit(1)
    if "if (!m_pMaterial)" not in body:
        print(f"FAIL: {name} lost its ordinary null guard", file=sys.stderr)
        raise SystemExit(1)
    if "m_pMaterial->IncrementReferenceCount()" not in body:
        print(f"FAIL: {name} no longer retains valid materials", file=sys.stderr)
        raise SystemExit(1)

if "(uintptr_t)m_pMaterial <" in set_material or "(uintptr_t)m_pMaterial <" in reference:
    print("FAIL: material pointer guard hides wrong-vtable dispatch instead of fixing it", file=sys.stderr)
    raise SystemExit(1)

print("PASS: VGUI material binding relies on the canonical ABI and ordinary null checks")
