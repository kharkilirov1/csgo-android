#!/bin/bash
cd ~/csgo-src
A=/opt/android-ndk-r20b/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android-addr2line
$A -e build/shaderapidx9/libshaderapidx9.so -f -C 0xE3C20 0xE264C
echo ===
$A -e build/materialsystem/libmaterialsystem.so -f -C 0x18EE0C 0x159D78
echo ===
$A -e build/engine/libengine.so -f -C 0xB27790 0xB26304 0x984BDC 0x984E78
