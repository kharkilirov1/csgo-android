#!/bin/bash
cd ~/csgo-src
A=/opt/android-ndk-r20b/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android-addr2line
$A -e build/game/client/libclient.so -f -C 0x127DA64 0x175989C
echo ===
$A -e build/engine/libengine.so -f -C 0xBE2A08 0xAB9620 0x82A4E0 0x82BE24 0x82DC24 0x82EC08 0x8489E8 0x847068
