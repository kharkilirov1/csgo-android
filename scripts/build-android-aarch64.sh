#!/bin/sh
# Build the CS:GO game for Android ARM64 (arm64-v8a / aarch64).
#
# Unlike build-android-armv7a.sh this uses NDK r20b, not r10e:
#   * r20b ships clang, which produces correct AArch64 code; the r10e GCC 4.9
#     toolchain predates usable arm64 support for a tree this size.
#   * API level 28 (not 21) is required because the cstrike tier1 string code
#     calls iconv_open/iconv/iconv_close, and Bionic only declares/implements
#     iconv from API 28 (__INTRODUCED_IN(28)). arm64 is 64-bit only, so a
#     modern (API 28 / Android 9) floor is reasonable anyway.
#
# Builds every module required at runtime, including the no-op Scaleform
# compatibility backend. The proprietary Autodesk GFx runtime is not part of
# this source tree, so Flash UI rendering remains intentionally unavailable.

set -eu

SRC=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
. "$SRC/scripts/android-aarch64-common.sh"

NDK_VERSION=${ANDROID_NDK_VERSION:-r20b}
NDK_DIR="$SRC/android-ndk-${NDK_VERSION}"
NDK_ZIP="android-ndk-${NDK_VERSION}-linux-x86_64.zip"
ANDROID_API_LEVEL=${ANDROID_API_LEVEL:-28}

case "$NDK_VERSION" in
	r20b) DEFAULT_NDK_SHA256=$ANDROID_NDK_R20B_SHA256 ;;
	*) DEFAULT_NDK_SHA256= ;;
esac
NDK_SHA256=${ANDROID_NDK_SHA256:-$DEFAULT_NDK_SHA256}

if [ -n "${ANDROID_NDK_HOME:-}" ]; then
	NDK_DIR=$ANDROID_NDK_HOME
elif [ -n "${NDK_HOME:-}" ]; then
	NDK_DIR=$NDK_HOME
fi

case "$NDK_DIR" in
	/*) ;;
	*) NDK_DIR="$SRC/$NDK_DIR" ;;
esac

git -C "$SRC" submodule update --init --recursive

if [ ! -d "$NDK_DIR" ]; then
	if [ -n "${ANDROID_NDK_HOME:-}${NDK_HOME:-}" ]; then
		echo "error: configured Android NDK directory does not exist: $NDK_DIR" >&2
		exit 1
	fi
	echo "==> downloading Android NDK $NDK_VERSION"
	NDK_ARCHIVE="$SRC/$NDK_ZIP"
	trap 'rm -f "$NDK_ARCHIVE"' EXIT HUP INT TERM
	wget -q "https://dl.google.com/android/repository/${NDK_ZIP}" -O "$NDK_ARCHIVE"
	if [ -z "$NDK_SHA256" ]; then
		echo "error: set ANDROID_NDK_SHA256 when downloading custom NDK $NDK_VERSION" >&2
		exit 1
	fi
	if ! command -v sha256sum >/dev/null 2>&1; then
		echo "error: sha256sum is required to verify the Android NDK archive" >&2
		exit 1
	fi
	printf '%s  %s\n' "$NDK_SHA256" "$NDK_ARCHIVE" | sha256sum -c -
	unzip -q "$NDK_ARCHIVE" -d "$SRC"
	rm -f "$NDK_ARCHIVE"
	trap - EXIT HUP INT TERM
fi

if [ ! -d "$NDK_DIR/toolchains/llvm/prebuilt" ]; then
	echo "error: invalid Android NDK directory: $NDK_DIR" >&2
	exit 1
fi

export ANDROID_NDK_HOME="$NDK_DIR"
export NDK_HOME="$NDK_DIR"

if command -v nproc >/dev/null 2>&1; then
	DEFAULT_JOBS=$(nproc)
else
	DEFAULT_JOBS=4
fi
BUILD_JOBS=${BUILD_JOBS:-$DEFAULT_JOBS}

cd "$SRC"
./waf configure -T debug --android="aarch64,clang,$ANDROID_API_LEVEL" --togles --build-games=csgo --disable-warns
./waf build -j "$BUILD_JOBS" --targets="$ANDROID_WAF_TARGETS"

echo "==> Android arm64 runtime modules built successfully"
