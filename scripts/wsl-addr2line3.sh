#!/bin/bash
cd ~/csgo-src
A=/opt/android-ndk-r20b/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android-addr2line
echo "===== engine ====="
$A -e build/engine/libengine.so -f -C 0x97EAF0 0x97EAD8 0x97E45C 0x9EB3C4 0x830400 0x97FBC4 0x98C394 0x9863F0 0xEFC5D4 0x984E44 0x9851E0 0x1249FC0 0x20BB54 0x1E6635 0x2367C9 0x22A886 0x13BCA98 0x1257689 0x23837B 0x23C71D
echo "===== client ====="
$A -e build/game/client/libclient.so -f -C 0x511C13
