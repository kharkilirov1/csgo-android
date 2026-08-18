#!/bin/bash
cd ~/csgo-src
A=/opt/android-ndk-r20b/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android-addr2line
$A -e build/game/client/libclient.so -f -C 0x1C8BD68 0x1C8BD60 0x1C8D6C0 0x1C8C194 0x1C8C324 0x1ADAE88 0x1AC5C20 0x1AC561C 0x1AC5874 0x1AD6A6C 0x1AD6CE0 0x1AD6EC8
