#!/bin/bash
cd ~/csgo-src
A=/opt/android-ndk-r20b/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android-addr2line
echo "=== shaderapidx9 ==="
$A -e build/materialsystem/shaderapidx9/libshaderapidx9.so -f -C 0x109380 0x10DBD8 0xFAE30 0xFBB54 0xD0248 0xD0378
echo "=== stdshader_dx9 ==="
$A -e build/materialsystem/stdshaders/libstdshader_dx9.so -f -C 0x1FEA14 0x19F790 0x18A7A0
echo "=== materialsystem ==="
$A -e build/materialsystem/libmaterialsystem.so -f -C 0x129CC8 0x129D90
