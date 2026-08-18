# Android external game-content contract

The APK contains the open-source engine/launcher and a small bootstrap VPK. It
does **not** contain, download, or repair Valve's proprietary CS:GO game data.
The user must select a compatible, legally obtained CS:GO content directory.

## Weapon-script preflight

Before `SDLActivity` starts, `ValveActivity2.preInit()` validates the selected
`csgo` directory on its existing background preparation thread:

1. `gameinfo.txt` must exist.
2. `scripts/weapon_manifest.txt` must be readable either from the native
   canonical VPK mount sequence or as a loose file.
3. The normalized manifest basename set must exactly match CS:GO `1.36.0.2`
   (build 572): 41 unique entries including `weapon_healthshot`.
4. Every declared basename must resolve to a plaintext
   `scripts/<basename>.txt` with a parseable `WeaponData` root and at least one
   non-empty KeyValues value. Empty/malformed placeholder files fail closed.

Encrypted `.ctx` files are deliberately **not** accepted by the Java
preflight. The native loader can decrypt them with ICE key `d7NSuLq2`, but an
opaque non-empty blob is not evidence that decryption and KeyValues parsing
will succeed. Until the exact native ICE loader is ported and tested, users
must restore the version-matched plaintext `.txt` closure from their legally
obtained content.

The pinned basename-set digest is SHA-256
`3d0463a142e614a1cd79cde97b470e538ea111bc2a11501a925b86306ae6051e`.
It is calculated over the sorted lowercase basenames, each followed by `\n`.
The source snapshot is
[SteamTracking/GameTracking-CS2 commit b6228c0](https://github.com/SteamTracking/GameTracking-CS2/blob/b6228c055e658edf6cd07d82baeabb31beb484bd/csgo/scripts/weapon_manifest.txt).

The preflight mirrors the Android native mount path: only exact lowercase
`pak01_dir.vpk` through `pak98_dir.vpk` are considered, and enumeration stops
at the first missing number. Files such as `backup_dir.vpk`, `pak03_dir.vpk`
after a `pak02` gap, and uppercase contract keys are not accepted. Mounted VPK
entries take precedence over loose files, exactly as `CBaseFileSystem::FindFile`
does on this build.

The native filesystem also prepends automatic sibling search paths before the
selected `csgo` directory. Until those overlays can be indexed with identical
precedence, the preflight fails closed when sibling `xlsppatch`, `update`, or an
active contiguous `csgo_dlc1`...`csgo_dlc99` directory exists. DLC discovery
stops at the first missing number or at the first directory containing
`dlc_disabled.txt`, matching `CBaseFileSystem::AddSearchPath`; therefore a
disabled `csgo_dlc1` or a lone `csgo_dlc2` is not mounted and is not rejected.

The VPK reader accepts directory format v1/v2, inline payloads, and external
archive chunks such as `pak01_000.vpk`. It validates required-entry CRCs and
overflow-safe bounds. V2 header section sizes must describe the exact file;
archive-MD5 entries, self hashes, and optional signature framing must have
their canonical structure. Trailing or structurally ambiguous footer bytes
fail closed.

The full scan runs once on `LauncherActivity`'s preparation worker. A
cryptographically random, process-local capability binds that successful
result to the canonical mod path and a cheap metadata fingerprint of the
automatic-overlay state and mounted VPK/weapon closure. `SDLActivity` reuses
the result only when the capability and fingerprint match. Creating or enabling
an automatic overlay after preparation invalidates the capability. A direct SDL
launch without this proof fails quickly instead of rescanning VPKs on the UI
thread.

Failure is fail-closed: the native game process is not started, the launcher
shows a content-specific error, and logcat receives the exact missing or
incompatible basename diagnostic.

## Deliberate limits

- The preflight indexes the canonical `pakNN` sequence and loose files directly
  inside the selected mod directory. It does not interpret arbitrary
  additional `SearchPaths` from customized `gameinfo.txt` files.
- It verifies the version-matched manifest closure, not ownership. The launcher
  cannot determine where a user's files came from.
- It never writes to the game directory and never substitutes generated weapon
  data. Missing content must be restored from the user's legitimate copy.

Run the focused host test with:

```text
python scripts/test_android_game_content_preflight.py
```
