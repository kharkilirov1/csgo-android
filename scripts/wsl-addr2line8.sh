#!/bin/bash
cd ~/csgo-src
A=/opt/android-ndk-r20b/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android-addr2line
$A -e build/game/client/libclient.so -f -C 0x9DF320 0x9DF29C 0xA047AC 0xA04784 0x1AD8E90 0x1AC2CAC 0x1AC2E30 0x1AD6970 0x1AD6C4C 0x1AD6E34 0xD5F45C 0xD69FAC
