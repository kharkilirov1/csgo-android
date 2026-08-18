#!/bin/bash
cd ~/csgo-src
A=/opt/android-ndk-r20b/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android-addr2line
$A -e build/vguimatsurface/libvguimatsurface.so -f -C 0x138AA0 0x1389E0 0x139494 0x1219E8 0x11864C
echo ===
$A -e build/game/client/libclient.so -f -C 0x1BA1830
echo ===
$A -e build/vgui2/libvgui2.so -f -C 0x7C94C
echo ===
$A -e build/engine/libengine.so -f -C 0xBE3400 0xBE3B48 0x9DFAB4
