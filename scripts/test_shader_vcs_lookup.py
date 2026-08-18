#!/usr/bin/env python3
"""Regression check for production VCS lookup paths."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SHADER_MANAGER = ROOT / "materialsystem/shaderapidx9/vertexshaderdx8.cpp"


def fail(message: str) -> int:
    print(f"FAIL: {message}")
    return 1


def function_slice(source: str, signature: str, next_signature: str) -> str:
    start = source.find(signature)
    if start < 0:
        raise ValueError(f"could not locate {signature}")

    end = source.find(next_signature, start + len(signature))
    if end < 0:
        raise ValueError(f"could not locate boundary {next_signature}")
    return source[start:end]


def main() -> int:
    source = SHADER_MANAGER.read_text(encoding="utf-8")
    try:
        open_shader = function_slice(
            source,
            "FileHandle_t CShaderManager::OpenFileAndLoadHeader",
            "void CShaderManager::WriteTranslatedFile",
        )
        load_shaders = function_slice(
            source,
            "bool CShaderManager::LoadAndCreateShaders(",
            "VertexShader_t CShaderManager::CreateVertexShader",
        )
    except ValueError as error:
        return fail(str(error))

    platform_open = (
        'g_pFullFileSystem->Open( pFileName, "rb", "PLATFORM" )'
    )
    if open_shader.count(platform_open) != 1:
        return fail("VCS files must be opened exactly once through PLATFORM")
    if 'g_pFullFileSystem->Open( pFileName, "rb", NULL )' in open_shader:
        return fail("Android VCS lookup bypasses PLATFORM with a NULL path ID")
    if 'getenv( "VALVE_GAME_PATH" )' not in open_shader:
        return fail("Android VCS lookup lacks an absolute mounted-platform fallback")
    if '"%s/platform/%s"' not in open_shader:
        return fail("Android VCS fallback is not rooted at VALVE_GAME_PATH/platform")
    if 'g_pFullFileSystem->Open( absolutePath, "rb", NULL )' not in open_shader:
        return fail("Android VCS fallback does not open the constructed absolute path")

    primary = (
        'Q_snprintf( filename, MAX_PATH, "shaders/%s/%s" '
        'SHADER_FNAME_EXTENSION, bVertexShader ? "vsh" : "psh", pName );'
    )
    fallback = (
        'Q_snprintf( filename, MAX_PATH, "shaders/fxc/%s" '
        'SHADER_FNAME_EXTENSION, pName );'
    )
    if "csgo/shaders/" in load_shaders:
        return fail("VCS lookup redundantly prefixes the mounted GAME directory")
    if load_shaders.count(primary) != 1:
        return fail("primary VCS lookup is not the portable shaders/vsh|psh path")
    if load_shaders.count(fallback) != 1:
        return fail("fallback VCS lookup is not the portable shaders/fxc path")

    primary_pos = load_shaders.index(primary)
    first_open_pos = load_shaders.index(
        "hFile = OpenFileAndLoadHeader( filename, pHeader );", primary_pos
    )
    fallback_pos = load_shaders.index(fallback, first_open_pos)
    second_open_pos = load_shaders.index(
        "hFile = OpenFileAndLoadHeader( filename, pHeader );", fallback_pos
    )
    if not primary_pos < first_open_pos < fallback_pos < second_open_pos:
        return fail("VCS lookup no longer tries vsh/psh before fxc")

    print("PASS: VCS lookup uses PLATFORM paths with a deterministic Android absolute fallback")
    return 0


if __name__ == "__main__":
    sys.exit(main())
