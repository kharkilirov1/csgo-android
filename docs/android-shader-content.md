# Android shader content release contract

## Distribution boundary

The APK is engine/bootstrap code only. It must not contain `.vcs` files,
including files nested inside `extras_dir.vpk` or another VPK. Shader bytecode
is external game content and is not published by this repository.

Use only content you are legally entitled to use: copy it from your own
compatible installation, or generate it locally from sources and tools you are
entitled to use. The verifier proves structure and completeness, not copyright,
license, ownership, or provenance. Provenance therefore remains a mandatory
human release gate.

## Complete external tree

The runtime mounts this tree as `PLATFORM/shaders`:

```text
shaders/
  fxc/
  vsh/
  psh/
```

`scripts/android_shader_release_contract.json` derives the required inventory
from the active Android `stdshader_dx9` source list, its recursive checked-in
DX9 helper includes, direct shader-name calls, and one parameterized legacy
pass. The current pinned inventory contains exactly **245** files:

- `fxc`: 243
- `vsh`: 1
- `psh`: 1

This is deliberately broader than the eight-file startup probe. The probe in
`scripts/shader_vcs_manifest.json` exists only to diagnose early renderer
startup and explicitly has `release_qualifying=false` and
`full_shader_coverage=false`.

## Preflight

Validate the checked-in contract itself:

```sh
python3 scripts/verify_android_shader_release.py contract
python3 scripts/verify_android_shader_release.py --json inventory
```

Validate a user-owned or locally generated `PLATFORM/shaders` directory:

```sh
python3 scripts/verify_android_shader_release.py content /path/to/platform/shaders
```

The content gate fails closed on missing, unexpected, duplicate/case-colliding,
symlinked, malformed, wrong-stage, or wrong-combo-geometry VCS files. It does
not require every possible combo to be materialized, because sparse compiled
records are valid VCS v6 containers. A publishable release still needs a
physical-device runtime witness that shader creation succeeds across the
declared smoke/map corpus.

Prove that a candidate APK keeps shader content external:

```sh
python3 scripts/verify_android_shader_release.py artifact path/to/app-release.apk
```

The artifact gate inspects both ZIP entries and every nested VPK directory
tree. `scripts/verify-android-release-apk.sh` invokes this gate for release
builds, so a candidate containing shader bytecode is rejected before upload.

## Current checkout status

The repository itself contains only four historical `shaders/fxc/*.vcs`
examples; they do not satisfy the 245-file external release inventory. A local
search performed during the 2026-08-14 release audit found no complete shader
corpus in the user's Steam installation or common user project/cache roots.
This is a content blocker, not a reason to bundle unknown/proprietary blobs.
