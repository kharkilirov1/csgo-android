#!/bin/bash
cd ~/csgo-src
A=/opt/android-ndk-r20b/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android-addr2line
$A -e build/game/client/libclient.so -f -C 0x1AF8B28 0x1AF6DA8 0x1AF7358 0x1AD9EB0 0x1AC62BC 0x1AC3168 0x1AC2EE0 0xD5F45C 0xD69FAC
