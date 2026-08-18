#!/bin/bash
cd ~/csgo-src
A=/opt/android-ndk-r20b/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android-addr2line
O=/opt/android-ndk-r20b/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android-objdump
N=/opt/android-ndk-r20b/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-nm
E=build/engine/libengine.so
echo "== ClientDLL_Init addr =="
$N $E | grep -w "_Z14ClientDLL_Initv" | head -2
ADDR=$($N $E | grep -w "_Z14ClientDLL_Initv" | awk '{print $1}' | head -1)
echo "addr=$ADDR"
echo "== disasm ClientDLL_Init, find Sys_Error calls =="
$O -d --no-show-raw-insn $E --start-address=0x$ADDR --stop-address=0x$((0x$ADDR + 0x400)) | grep -B8 "bl.*Sys_Error" | head -40
echo "== addr2line of crash return addresses in FRESH engine =="
$A -e $E -f -C 0x9EB3C4 0x830400 0x97FBC4 0x98C394 0x97EAF0
