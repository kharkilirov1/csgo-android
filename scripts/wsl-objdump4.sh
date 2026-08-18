#!/bin/bash
cd ~/csgo-src
O=/opt/android-ndk-r20b/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android-objdump
$O -d --no-show-raw-insn --start-address=0x1af8a20 --stop-address=0x1af8a98 build/game/client/libclient.so
