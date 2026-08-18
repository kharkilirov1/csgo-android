#!/bin/bash
cd ~/csgo-src
A=/opt/android-ndk-r20b/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android-addr2line
echo "=== shaderapidx9 ==="
$A -e build/materialsystem/shaderapidx9/libshaderapidx9.so -f -C 0xFB6DC 0xFB6CC 0xAD770 0xACE80 0xADD48 0xA1338 0x9776C 0x977F0
echo "=== vguimatsurface ==="
$A -e build/vguimatsurface/libvguimatsurface.so -f -C 0x11A40C
