#!/bin/bash
cd ~/csgo-src
A=/opt/android-ndk-r20b/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android-addr2line
$A -e build/shaderapidx9/libshaderapidx9.so -f -C 0xFB62C 0xFB604 0xAD6A8 0xACDB8 0xADC80 0xA1270 0x976A4 0x97728
echo ===
$A -e build/vguimatsurface/libvguimatsurface.so -f -C 0x11B360
