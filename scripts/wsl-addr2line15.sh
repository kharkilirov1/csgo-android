#!/bin/bash
cd ~/csgo-src
A=/opt/android-ndk-r20b/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android-addr2line
$A -e build/materialsystem/shaderapidx9/libshaderapidx9.so -f -C 0xE3C20 0xE264C
