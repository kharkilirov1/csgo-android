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
# The server game DLL (libserver.so) builds and links cleanly. The client is
# not built here yet: its Scaleform UI backend (proprietary Autodesk GFx) is
# absent, so ScaleformUI() is unresolved at link time. Add the client target
# once a Scaleform stub / VGUI replacement is in place.

set -e

NDK_VERSION=r20b
NDK_DIR="android-ndk-${NDK_VERSION}"
NDK_ZIP="android-ndk-${NDK_VERSION}-linux-x86_64.zip"

git submodule init && git submodule update

if [ ! -d "$NDK_DIR" ]; then
	wget -q "https://dl.google.com/android/repository/${NDK_ZIP}" -O "$NDK_ZIP"
	unzip -q "$NDK_ZIP"
	rm -f "$NDK_ZIP"
fi

export ANDROID_NDK_HOME="$PWD/$NDK_DIR"
export NDK_HOME="$PWD/$NDK_DIR"

./waf configure -T debug --android=aarch64,clang,28 --togles --build-games=csgo --disable-warns
./waf build --targets=server
