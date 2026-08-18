#!/bin/bash
cd ~/csgo-src
A=/opt/android-ndk-r20b/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android-addr2line
$A -e build/game/client/libclient.so -f -C 0x1AF8A7C 0x1AF6D20 0x1AF72D0 0x1AD9EB0 0x1AC62BC 0x1AC3188 0x1AC2EE0 0x1AD6970 0x1AD6C4C 0x1AD6E34 0xD5F45C 0xD69FAC 0xBBC2B4
