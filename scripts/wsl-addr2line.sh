#!/bin/bash
cd ~/csgo-src
A=/opt/android-ndk-r20b/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android-addr2line
echo "== vgui2 0x61390 0x612DC =="
$A -e build/vgui2/src/libvgui2.so -f -C 0x61390 0x612DC
echo "== launcher 0x68864 =="
$A -e build/launcher/liblauncher.so -f -C 0x68864
echo "== launcher 0x68800-0x68900 context =="
$A -e build/launcher/liblauncher.so -f -C 0x68800 0x68820 0x68840 0x68860 0x68880 0x688A0
