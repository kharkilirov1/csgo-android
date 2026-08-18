#!/bin/bash
cd ~/csgo-src
A=/opt/android-ndk-r20b/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android-addr2line
O=/opt/android-ndk-r20b/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android-objdump
N=/opt/android-ndk-r20b/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-nm
echo "== ClientDLL_Init symbol in fresh libclient.so =="
$N build/game/client/libclient.so | grep -i "ClientDLL_Init" | head -3
echo "== fresh addr2line of crash addresses =="
$A -e build/game/client/libclient.so -f -C 0x9EB3C4 0x9EB3B8 0x9EB3A0 0x9EB3E4 0x830400
echo "== disasm around 0x9EB3A0 in FRESH binary =="
$O -d --no-show-raw-insn --start-address=0x9EB380 --stop-address=0x9EB400 build/game/client/libclient.so
