#!/bin/sh
# Verify the properties that distinguish a publishable release APK from a
# merely installable debug artifact.

set -eu

SRC=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
. "$SRC/scripts/android-aarch64-common.sh"

APK=${1:-}
if [ -z "$APK" ] || [ ! -f "$APK" ]; then
	echo "usage: $0 path/to/app-release.apk" >&2
	exit 1
fi

SDK=${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}
BUILD_TOOLS_VERSION=${ANDROID_BUILD_TOOLS_VERSION:-35.0.0}
if [ -n "$SDK" ]; then
	BUILD_TOOLS="$SDK/build-tools/$BUILD_TOOLS_VERSION"
else
	BUILD_TOOLS=
fi
APKSIGNER=${APKSIGNER:-"$BUILD_TOOLS/apksigner"}
ZIPALIGN=${ZIPALIGN:-"$BUILD_TOOLS/zipalign"}
AAPT2=${AAPT2:-"$BUILD_TOOLS/aapt2"}

for tool in "$APKSIGNER" "$ZIPALIGN" "$AAPT2" unzip cmp sha256sum strings; do
	if ! command -v "$tool" >/dev/null 2>&1; then
		echo "error: required release verifier tool is unavailable: $tool" >&2
		exit 1
	fi
done

if [ -z "${CSGO_RELEASE_CERT_SHA256:-}" ]; then
	echo "error: CSGO_RELEASE_CERT_SHA256 is required to pin the release signer" >&2
	exit 1
fi
if [ -z "${CSGO_VERSION_CODE:-}" ] || [ -z "${CSGO_VERSION_NAME:-}" ]; then
	echo "error: CSGO_VERSION_CODE and CSGO_VERSION_NAME are required to verify release identity" >&2
	exit 1
fi
case "$CSGO_VERSION_CODE" in
	*[!0-9]*|0)
		echo "error: CSGO_VERSION_CODE must be a positive integer" >&2
		exit 1
		;;
esac
if [ "$CSGO_VERSION_CODE" -gt 2100000000 ]; then
	echo "error: CSGO_VERSION_CODE exceeds Android's 2100000000 limit" >&2
	exit 1
fi
if ! printf '%s\n' "$CSGO_VERSION_NAME" | grep -Eq '^[0-9A-Za-z][0-9A-Za-z._+-]{0,99}$'; then
	echo "error: CSGO_VERSION_NAME must use 1-100 safe ASCII characters" >&2
	exit 1
fi

normalize_digest() {
	printf '%s' "$1" | tr -d '[:space:]:' | tr '[:upper:]' '[:lower:]'
}

expected_cert=$(normalize_digest "$CSGO_RELEASE_CERT_SHA256")
case "$expected_cert" in
	*[!0-9a-f]*|'')
		echo "error: CSGO_RELEASE_CERT_SHA256 must be a hexadecimal SHA-256 digest" >&2
		exit 1
		;;
esac
if [ "${#expected_cert}" -ne 64 ]; then
	echo "error: CSGO_RELEASE_CERT_SHA256 must contain exactly 64 hexadecimal digits" >&2
	exit 1
fi

"$ZIPALIGN" -c -P 16 4 "$APK"
signature_output=$("$APKSIGNER" verify \
	--verbose \
	--print-certs \
	--min-sdk-version 28 \
	"$APK")

if ! printf '%s\n' "$signature_output" |
	grep -Eq '^Verified using v(2|3) scheme .*: true$'; then
	echo "error: release APK has neither a verified v2 nor v3 signature" >&2
	exit 1
fi

cert_digests=$(printf '%s\n' "$signature_output" |
	sed -n 's/^Signer #[0-9][0-9]* certificate SHA-256 digest: //p')
cert_count=$(printf '%s\n' "$cert_digests" | sed '/^$/d' | wc -l | tr -d ' ')
if [ "$cert_count" -ne 1 ]; then
	echo "error: release APK must have exactly one signer (found $cert_count)" >&2
	exit 1
fi
actual_cert=$(normalize_digest "$cert_digests")
if [ "$actual_cert" != "$expected_cert" ]; then
	echo "error: release APK signer does not match CSGO_RELEASE_CERT_SHA256" >&2
	echo "actual signer SHA-256: $actual_cert" >&2
	exit 1
fi

badging=$("$AAPT2" dump badging "$APK")
if ! printf '%s\n' "$badging" | grep -Fq "package: name='com.kharki.csgo'"; then
	echo "error: release APK has the wrong applicationId" >&2
	exit 1
fi
actual_version_code=$(printf '%s\n' "$badging" |
	sed -n "s/.*versionCode='\([^']*\)'.*/\1/p" | head -n 1)
actual_version_name=$(printf '%s\n' "$badging" |
	sed -n "s/.*versionName='\([^']*\)'.*/\1/p" | head -n 1)
if [ "$actual_version_code" != "$CSGO_VERSION_CODE" ] ||
	[ "$actual_version_name" != "$CSGO_VERSION_NAME" ]; then
	echo "error: release APK identity does not match requested version" >&2
	echo "expected: versionCode=$CSGO_VERSION_CODE versionName=$CSGO_VERSION_NAME" >&2
	echo "actual: versionCode=$actual_version_code versionName=$actual_version_name" >&2
	exit 1
fi
if printf '%s\n' "$badging" | grep -Fq 'application-debuggable'; then
	echo "error: release APK is application-debuggable" >&2
	exit 1
fi

entries=$(unzip -Z1 "$APK")
unexpected_native_entries=$(printf '%s\n' "$entries" |
	grep -E '^lib/' |
	grep -Ev '^lib/arm64-v8a/[^/]+\.so$' || true)
if [ -n "$unexpected_native_entries" ]; then
	echo "error: release APK contains native payload outside arm64-v8a:" >&2
	printf '%s\n' "$unexpected_native_entries" >&2
	exit 1
fi

TMPDIR_RELEASE=$(mktemp -d)
trap 'rm -rf "$TMPDIR_RELEASE"' EXIT HUP INT TERM
expected_native_count=0
for library in $ANDROID_REQUIRED_LIBRARIES; do
	library_entry="lib/arm64-v8a/$library"
	library_count=$(printf '%s\n' "$entries" | grep -Fxc "$library_entry" || true)
	if [ "$library_count" -ne 1 ]; then
		echo "error: release APK must contain exactly one $library_entry (found $library_count)" >&2
		exit 1
	fi
	expected_native_count=$((expected_native_count + 1))
done
actual_native_count=$(printf '%s\n' "$entries" |
	grep -Ec '^lib/arm64-v8a/[^/]+\.so$' || true)
if [ "$actual_native_count" -ne "$expected_native_count" ]; then
	echo "error: release APK native allowlist mismatch: expected $expected_native_count entries, found $actual_native_count" >&2
	exit 1
fi

unzip -p "$APK" "lib/arm64-v8a/libdatacache.so" > "$TMPDIR_RELEASE/libdatacache.so"
for interface_version in VPrecacheSystem001 VResourceAccessControl001; do
	if ! strings -a "$TMPDIR_RELEASE/libdatacache.so" | grep -Fxq "$interface_version"; then
		echo "error: packaged libdatacache.so lacks $interface_version" >&2
		exit 1
	fi
done

for asset in LICENSE thirdpartylegalnotices.txt; do
	asset_path="assets/legal/$asset"
	asset_count=$(printf '%s\n' "$entries" | grep -Fxc "$asset_path" || true)
	if [ "$asset_count" -ne 1 ]; then
		echo "error: release APK must contain exactly one $asset_path (found $asset_count)" >&2
		exit 1
	fi
	unzip -p "$APK" "$asset_path" > "$TMPDIR_RELEASE/$asset"
	if ! cmp -s "$SRC/$asset" "$TMPDIR_RELEASE/$asset"; then
		echo "error: packaged $asset_path differs from repository $asset" >&2
		exit 1
	fi
done

# Prove that the release-only bootstrap path was actually used. A VPK with the
# shaders merely omitted could satisfy the shader gate while silently dropping
# unrelated bootstrap data, so compare the packaged bytes with a fresh,
# fail-closed deterministic sanitization of the tracked debug asset.
bootstrap_path="assets/extras_dir.vpk"
bootstrap_count=$(printf '%s\n' "$entries" | grep -Fxc "$bootstrap_path" || true)
if [ "$bootstrap_count" -ne 1 ]; then
	echo "error: release APK must contain exactly one $bootstrap_path (found $bootstrap_count)" >&2
	exit 1
fi
unzip -p "$APK" "$bootstrap_path" > "$TMPDIR_RELEASE/packaged-extras_dir.vpk"
python3 "$SRC/scripts/sanitize_android_release_vpk.py" \
	"$SRC/android/csgo-launcher/assets/extras_dir.vpk" \
	"$TMPDIR_RELEASE/expected-extras_dir.vpk" --json \
	> "$TMPDIR_RELEASE/sanitizer-report.json"
if ! cmp -s \
	"$TMPDIR_RELEASE/expected-extras_dir.vpk" \
	"$TMPDIR_RELEASE/packaged-extras_dir.vpk"; then
	echo "error: packaged $bootstrap_path is not the deterministic sanitized release VPK" >&2
	exit 1
fi

# Publication artifacts must not redistribute VCS shader bytecode.  Runtime
# shader content is a separately validated, user-owned/local-install payload.
python3 "$SRC/scripts/verify_android_shader_release.py" contract
python3 "$SRC/scripts/verify_android_shader_release.py" artifact "$APK"

apk_sha256=$(sha256sum "$APK" | awk '{print $1}')
echo "Release APK verified: package=com.kharki.csgo versionCode=$actual_version_code versionName=$actual_version_name abi=arm64-v8a signer=$actual_cert sha256=$apk_sha256"
