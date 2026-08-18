#!/bin/bash
cd ~/csgo-src
A=/opt/android-ndk-r20b/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android-addr2line
echo "===== client frames ====="
$A -e build/game/client/libclient.so -f -C 0x1C8B584 0x1C8B57C 0x1ADADF4 0x1AC5B8C 0x1AC5588 0x1AC57E0 0x1AD69D8 0x1AD6C4C 0x1AD6E34 0xD5F45C 0xD69FAC 0xBBC2B4
