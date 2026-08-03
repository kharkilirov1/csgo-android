#!/bin/sh
# Package the arm64 engine into an installable APK.
#
# Run scripts/build-android-aarch64.sh first - this only collects what that
# produced. Needs ANDROID_HOME pointing at an SDK with platform 35 and
# build-tools 35, plus the NDK used for the native build (for llvm-strip).
#
# The result is android/csgo-launcher/app/build/outputs/apk/debug/app-debug.apk,
# signed with the local debug key.
#
# NOTE: this packages the engine only. The APK contains no game content - maps,
# models, materials and sounds have to come from a CS:GO installation and be
# placed where the launcher's directory picker points.

set -e

SRC="$(cd "$(dirname "$0")/.." && pwd)"
LAUNCHER="$SRC/android/csgo-launcher"
JNI="$LAUNCHER/jniLibs/arm64-v8a"
NDK="${ANDROID_NDK_HOME:-${NDK_HOME:-$SRC/android-ndk-r20b}}"

if [ -z "$ANDROID_HOME" ] && [ -z "$ANDROID_SDK_ROOT" ]; then
	echo "error: set ANDROID_HOME (or ANDROID_SDK_ROOT) to your Android SDK" >&2
	exit 1
fi
SDK="${ANDROID_HOME:-$ANDROID_SDK_ROOT}"

if [ ! -d "$SRC/build" ]; then
	echo "error: no build/ - run scripts/build-android-aarch64.sh first" >&2
	exit 1
fi

echo "==> collecting arm64 shared libraries"
rm -rf "$JNI"
mkdir -p "$JNI"

# Everything the waf build produced for this ABI.
find "$SRC/build" -name '*.so' | while read -r so; do
	if file "$so" | grep -q aarch64; then
		cp "$so" "$JNI/"
	fi
done

# SDL2 ships prebuilt; libc++_shared comes from the NDK because the engine is
# linked against the shared STL.
cp "$SRC/lib/android/aarch64/libSDL2.so" "$JNI/"
find "$NDK" -name 'libc++_shared.so' -path '*aarch64*' | head -1 | xargs -I{} cp {} "$JNI/"

echo "==> stripping ($(du -sh "$JNI" | cut -f1) unstripped)"
STRIP=$(find "$NDK" -name 'llvm-strip' | head -1)
for so in "$JNI"/*.so; do
	"$STRIP" --strip-all "$so" 2>/dev/null || true
done
echo "    -> $(du -sh "$JNI" | cut -f1), $(ls "$JNI" | wc -l) libraries"

echo "sdk.dir=$SDK" > "$LAUNCHER/local.properties"

echo "==> gradle assembleDebug"
cd "$LAUNCHER"
if [ -x ./gradlew ]; then
	./gradlew --no-daemon assembleDebug
else
	gradle --no-daemon assembleDebug
fi

APK="$LAUNCHER/app/build/outputs/apk/debug/app-debug.apk"
echo
echo "==> $APK ($(ls -lh "$APK" | awk '{print $5}'))"
