#!/bin/sh
# Package the arm64 engine into an installable APK.
#
# Run scripts/build-android-aarch64.sh first. This collects only the declared
# runtime payload and fails if a module, ABI or transitive dependency is wrong.
# ANDROID_HOME (or ANDROID_SDK_ROOT) must point at an SDK with platform 35.
#
# The result is android/csgo-launcher/app/build/outputs/apk/debug/app-debug.apk,
# signed with the local debug key.
#
# NOTE: extras_dir.vpk contains only launcher/bootstrap support files. Maps,
# models, materials and sounds still have to come from a CS:GO installation.

set -eu

SRC=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
. "$SRC/scripts/android-aarch64-common.sh"
LAUNCHER="$SRC/android/csgo-launcher"
JNI="$LAUNCHER/jniLibs/arm64-v8a"
NDK="${ANDROID_NDK_HOME:-${NDK_HOME:-$SRC/android-ndk-r20b}}"
export GRADLE_USER_HOME=${GRADLE_USER_HOME:-"$SRC/.gradle"}
export ANDROID_USER_HOME=${ANDROID_USER_HOME:-"$GRADLE_USER_HOME/android-user"}
mkdir -p "$GRADLE_USER_HOME" "$ANDROID_USER_HOME"

if [ -z "${ANDROID_HOME:-}" ] && [ -z "${ANDROID_SDK_ROOT:-}" ]; then
	echo "error: set ANDROID_HOME (or ANDROID_SDK_ROOT) to your Android SDK" >&2
	exit 1
fi
SDK="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}"

case "$NDK" in
	/*) ;;
	*) NDK="$SRC/$NDK" ;;
esac

case "$SDK" in
	/*) ;;
	*) SDK=$(CDPATH= cd -- "$SDK" && pwd) ;;
esac

if [ ! -d "$SRC/build" ]; then
	echo "error: no build/ - run scripts/build-android-aarch64.sh first" >&2
	exit 1
fi

if [ ! -d "$NDK" ]; then
	echo "error: Android NDK directory does not exist: $NDK" >&2
	exit 1
fi

echo "==> collecting arm64 shared libraries"
mkdir -p "$JNI"
# jniLibs is generated output. Clear regular files and stale symlinks from a
# previous run so Gradle cannot silently package an undeclared native module.
find "$JNI" -mindepth 1 -maxdepth 1 \
	\( -type f -o -type l \) \
	\( -name '*.so' -o -name '.dependency-errors' \) -delete

# Copy only the runtime modules declared in android-aarch64-common.sh. Refuse
# ambiguous duplicate basenames so stale build directories cannot silently win.
for library in $ANDROID_REQUIRED_LIBRARIES; do
	case "$library" in
		libSDL2.so|libc++_shared.so) continue ;;
	esac

	matches=$(find "$SRC/build" -type f -name "$library" -print)
	match_count=$(printf '%s\n' "$matches" | sed '/^$/d' | wc -l | tr -d ' ')
	if [ "$match_count" -eq 0 ]; then
		echo "error: missing $library; run scripts/build-android-aarch64.sh" >&2
		exit 1
	fi
	if [ "$match_count" -ne 1 ]; then
		echo "error: multiple build outputs named $library:" >&2
		printf '%s\n' "$matches" >&2
		exit 1
	fi
	cp "$matches" "$JNI/$library"
done

# SDL2 ships prebuilt; libc++_shared comes from the NDK because the engine is
# linked against the shared STL.
cp "$SRC/lib/android/aarch64/libSDL2.so" "$JNI/libSDL2.so"
libcxx_matches=$(find "$NDK" -type f -name 'libc++_shared.so' -path '*aarch64*' -print)
libcxx_count=$(printf '%s\n' "$libcxx_matches" | sed '/^$/d' | wc -l | tr -d ' ')
if [ "$libcxx_count" -eq 0 ]; then
	echo "error: no AArch64 libc++_shared.so found under $NDK" >&2
	exit 1
fi
if [ "$libcxx_count" -ne 1 ]; then
	echo "error: multiple AArch64 libc++_shared.so candidates under $NDK:" >&2
	printf '%s\n' "$libcxx_matches" >&2
	exit 1
fi
libcxx=$(printf '%s\n' "$libcxx_matches" | sed -n '1p')
cp "$libcxx" "$JNI/libc++_shared.so"

echo "==> stripping ($(du -sh "$JNI" | cut -f1) unstripped)"
STRIP=$(find "$NDK" -type f -name 'llvm-strip' -print | sed -n '1p')
if [ -z "$STRIP" ]; then
	echo "error: llvm-strip not found under $NDK" >&2
	exit 1
fi
for so in "$JNI"/*.so; do
	# Debug sections account for hundreds of MiB in this tree. Dynamic exports
	# required by JNI/dlsym live in .dynsym and remain available after strip-all;
	# verify-android-aarch64-libs.sh checks them immediately below.
	"$STRIP" --strip-all "$so"
done
echo "    -> $(du -sh "$JNI" | cut -f1), $(ls "$JNI" | wc -l) libraries"

READELF=$(find "$NDK" -type f \( -name 'llvm-readelf' -o -name 'aarch64-linux-android-readelf' \) -print | sed -n '1p')
if [ -z "$READELF" ]; then
	READELF=readelf
fi
READELF="$READELF" "$SRC/scripts/verify-android-aarch64-libs.sh" "$JNI"

printf 'sdk.dir=%s\n' "$SDK" > "$LAUNCHER/local.properties"

echo "==> gradle assembleDebug"
cd "$LAUNCHER"
if [ ! -f ./gradlew ] || [ ! -f ./gradle/wrapper/gradle-wrapper.jar ]; then
	echo "error: Gradle wrapper is incomplete" >&2
	exit 1
fi
./gradlew --no-daemon --stacktrace assembleDebug

APK="$LAUNCHER/app/build/outputs/apk/debug/app-debug.apk"
if [ ! -f "$APK" ]; then
	echo "error: Gradle did not produce $APK" >&2
	exit 1
fi

BUILD_TOOLS_VERSION=${ANDROID_BUILD_TOOLS_VERSION:-35.0.0}
BUILD_TOOLS="$SDK/build-tools/$BUILD_TOOLS_VERSION"
if [ ! -x "$BUILD_TOOLS/apksigner" ] || [ ! -x "$BUILD_TOOLS/zipalign" ]; then
	echo "error: Android SDK build-tools $BUILD_TOOLS_VERSION with apksigner and zipalign are required" >&2
	exit 1
fi

"$BUILD_TOOLS/apksigner" verify --verbose "$APK"
"$BUILD_TOOLS/zipalign" -c -P 16 4 "$APK"

for library in $ANDROID_REQUIRED_LIBRARIES; do
	if ! unzip -Z1 "$APK" | grep -Fxq "lib/arm64-v8a/$library"; then
		echo "error: APK is missing lib/arm64-v8a/$library" >&2
		exit 1
	fi
done

echo
echo "==> $APK ($(ls -lh "$APK" | awk '{print $5}'))"
