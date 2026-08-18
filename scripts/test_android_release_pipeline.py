#!/usr/bin/env python3
"""Guard the fail-closed Android release-candidate packaging contract."""

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "publish-apk.yml"
GRADLE = ROOT / "android" / "csgo-launcher" / "app" / "build.gradle"
BUILD_SCRIPT = ROOT / "scripts" / "build-apk-aarch64.sh"
VERIFY_SCRIPT = ROOT / "scripts" / "verify-android-release-apk.sh"
LICENSE = ROOT / "LICENSE"
NOTICES = ROOT / "thirdpartylegalnotices.txt"
WRAPPER_PROPERTIES = (
    ROOT
    / "android"
    / "csgo-launcher"
    / "gradle"
    / "wrapper"
    / "gradle-wrapper.properties"
)
VERIFICATION_METADATA = (
    ROOT
    / "android"
    / "csgo-launcher"
    / "gradle"
    / "verification-metadata.xml"
)
UPDATE_SERVICE = (
    ROOT / "android" / "csgo-launcher" / "src" / "me" / "nillerusr" / "UpdateService.java"
)


def main() -> int:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    gradle = GRADLE.read_text(encoding="utf-8")
    build_script = BUILD_SCRIPT.read_text(encoding="utf-8")
    verify_script = VERIFY_SCRIPT.read_text(encoding="utf-8") if VERIFY_SCRIPT.is_file() else ""
    update_service = UPDATE_SERVICE.read_text(encoding="utf-8")
    wrapper_properties = WRAPPER_PROPERTIES.read_text(encoding="utf-8")
    failures: list[str] = []

    workflow_lines = workflow.splitlines()
    workflow_triggers: list[str] = []
    try:
        on_index = workflow_lines.index("on:")
    except ValueError:
        on_index = -1
    if on_index >= 0:
        for line in workflow_lines[on_index + 1 :]:
            if line and not line[0].isspace():
                break
            trigger = re.fullmatch(r"  ([A-Za-z_][A-Za-z0-9_-]*):", line)
            if trigger:
                workflow_triggers.append(trigger.group(1))
    if workflow_triggers != ["workflow_dispatch"]:
        failures.append(
            "publish workflow must have only workflow_dispatch, found "
            f"{workflow_triggers or 'none'}"
        )
    if not re.search(r"(?m)^\s+confirm_release_candidate:\s*$", workflow):
        failures.append("manual workflow lacks an explicit release-candidate confirmation input")
    if "if: ${{ inputs.confirm_release_candidate }}" not in workflow:
        failures.append("release-candidate job is not gated by the confirmation input")
    if not re.search(r"(?m)^\s+contents:\s+read\s*$", workflow):
        failures.append("workflow permissions are not read-only")
    forbidden_publishers = (
        "contents: write",
        "gh release ",
        "softprops/action-gh-release",
        "ncipollo/release-action",
    )
    for token in forbidden_publishers:
        if token in workflow:
            failures.append(f"workflow can publish externally via {token!r}")
    for debug_artifact_token in ("assembleDebug", "app-debug.apk", "debug-signed"):
        if debug_artifact_token in workflow:
            failures.append(f"release workflow still packages debug output via {debug_artifact_token!r}")

    expected_actions = (
        "actions/checkout@11d5960a326750d5838078e36cf38b85af677262",
        "actions/setup-java@cf277c60eb25467037889841efdb72551f06f6c3",
        "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
    )
    for action in expected_actions:
        if action not in workflow:
            failures.append(f"workflow action is not pinned to reviewed commit {action!r}")
    if re.search(r"(?m)^\s*-?\s*uses:\s*[^\s]+@v\d+\s*$", workflow):
        failures.append("workflow contains a mutable major-version action tag")
    if "2d2d50857e4eb553af5a6dc3ad507a17adf43d115264b1afc116f95c92e5e258" not in workflow:
        failures.append("Android command-line tools download lacks its pinned SHA-256")
    upload_index = workflow.find("actions/upload-artifact@")
    cleanup_index = workflow.find('rm -f "$RUNNER_TEMP/csgo-release.keystore"')
    if cleanup_index < 0 or upload_index < 0 or cleanup_index > upload_index:
        failures.append("release keystore is not removed before artifact upload action")

    required_workflow_tokens = (
        "python3 scripts/test_datacache_waf_parity.py",
        "python3 scripts/test_sanitize_android_release_vpk.py",
        "python3 scripts/test_android_shader_release.py",
        "python3 scripts/test_android_game_content_preflight.py",
        "CSGO_BUILD_VARIANT: release",
        "CSGO_RELEASE_KEYSTORE_B64",
        "CSGO_RELEASE_KEYSTORE_PASSWORD",
        "CSGO_RELEASE_KEY_ALIAS",
        "CSGO_RELEASE_KEY_PASSWORD",
        "CSGO_RELEASE_CERT_SHA256",
        'license_status=${PIPESTATUS[1]}',
        "app/build/outputs/apk/release/app-release.apk",
    )
    for token in required_workflow_tokens:
        if token not in workflow:
            failures.append(f"workflow lacks release contract token {token!r}")

    required_gradle_tokens = (
        'environmentVariable("CSGO_RELEASE_KEYSTORE")',
        'environmentVariable("CSGO_RELEASE_KEYSTORE_PASSWORD")',
        'environmentVariable("CSGO_RELEASE_KEY_ALIAS")',
        'environmentVariable("CSGO_RELEASE_KEY_PASSWORD")',
        "signingConfigs",
        "taskGraph.whenReady",
        "release {",
        "debuggable false",
        "generateLegalAssets",
        'environmentVariable("CSGO_RELEASE_BOOTSTRAP_ASSETS")',
        'environmentVariable("CSGO_VERSION_CODE")',
        'environmentVariable("CSGO_VERSION_NAME")',
        'environmentVariable("CSGO_RELEASE_PIPELINE")',
        'releasePipelineGuard != "android-release-wrapper-v1"',
        "SANITIZED_RELEASE_BOOTSTRAP_SHA256",
        'assets.srcDirs = ["../assets"]',
        '"LICENSE"',
        '"thirdpartylegalnotices.txt"',
    )
    for token in required_gradle_tokens:
        if token not in gradle:
            failures.append(f"Gradle release configuration lacks {token!r}")

    required_build_tokens = (
        'CSGO_BUILD_VARIANT=${CSGO_BUILD_VARIANT:-debug}',
        "assembleRelease",
        "app-release.apk",
        "verify-android-release-apk.sh",
        "sanitize_android_release_vpk.py",
        "CSGO_RELEASE_BOOTSTRAP_ASSETS",
        "unset CSGO_RELEASE_PIPELINE",
        "export CSGO_RELEASE_PIPELINE=android-release-wrapper-v1",
        "CSGO_RELEASE_CERT_SHA256",
        "CSGO_VERSION_CODE",
        "CSGO_VERSION_NAME",
    )
    for token in required_build_tokens:
        if token not in build_script:
            failures.append(f"APK build script lacks {token!r}")

    main_source_set = re.search(r"(?ms)^\s*main\s*\{(.*?)^\s*\}", gradle)
    if main_source_set is None:
        failures.append("Gradle configuration lacks a main source set")
    elif '"../assets"' in main_source_set.group(1):
        failures.append("tracked debug assets still leak through the main/release source set")

    required_verifier_tokens = (
        "apksigner",
        "zipalign",
        "aapt2",
        "CSGO_RELEASE_CERT_SHA256",
        'asset_path="assets/legal/$asset"',
        "LICENSE thirdpartylegalnotices.txt",
        "application-debuggable",
        "lib/arm64-v8a/",
        "VPrecacheSystem001",
        "VResourceAccessControl001",
        "sanitize_android_release_vpk.py",
        'bootstrap_path="assets/extras_dir.vpk"',
        'verify_android_shader_release.py" contract',
        'verify_android_shader_release.py" artifact "$APK"',
        "actual_native_count",
        "expected_native_count",
    )
    for token in required_verifier_tokens:
        if token not in verify_script:
            failures.append(f"release APK verifier lacks {token!r}")

    if "distributionSha256Sum=544c35d6bd849ae8a5ed0bcea39ba677dc40f49df7d1835561582da2009b961d" not in wrapper_properties:
        failures.append("Gradle wrapper distribution is not SHA-256 pinned")
    if not VERIFICATION_METADATA.is_file() or VERIFICATION_METADATA.stat().st_size == 0:
        failures.append("Gradle dependency verification metadata is missing")

    for legal_file in (LICENSE, NOTICES):
        if not legal_file.is_file() or legal_file.stat().st_size == 0:
            failures.append(f"required legal file is missing or empty: {legal_file.name}")

    pending_intent_calls = re.findall(
        r"PendingIntent\.getActivity\s*\((.*?)\)\s*;",
        update_service,
        re.DOTALL,
    )
    if not pending_intent_calls:
        failures.append("UpdateService no longer exposes its notification PendingIntent")
    for call in pending_intent_calls:
        if "PendingIntent.FLAG_IMMUTABLE" not in call and "PendingIntent.FLAG_MUTABLE" not in call:
            failures.append("UpdateService PendingIntent lacks an explicit mutability flag")

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1

    print("PASS: Android release pipeline is manual, release-signed, and packages legal notices")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
