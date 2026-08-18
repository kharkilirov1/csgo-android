#!/bin/bash
cd ~/csgo-src
A=/opt/android-ndk-r20b/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android-addr2line
echo "===== client ====="
$A -e build/game/client/libclient.so -f -C 0x1C8B2E0 0x1C8B2D8 0x1C8CBE4 0x1C8B70C 0x1C8B848 0x1ADAB50 0x1AC5934 0x1AC5408 0x1AC5660 0x1AD6780 0x1AD69F4 0x1AD6B90 0xD5F45C 0xD69FAC 0xBBC2B4 0x1E39728 0x2015380 0x289D8D8 0x4F68D5 0x563FDE 0x4FED6A 0x6971F08 0x549427 0x53178E 0x531779 0x2015428
echo "===== materialsystem ====="
$A -e build/materialsystem/libmaterialsystem.so -f -C 0x2E3DE0
echo "===== engine ====="
$A -e build/engine/libengine.so -f -C 0x97F5D0
echo "===== vstdlib ====="
$A -e build/vstdlib/libvstdlib.so -f -C 0x56D80
echo "===== soundemittersystem ====="
$A -e build/soundemittersystem/libsoundemittersystem.so -f -C 0x4054C
