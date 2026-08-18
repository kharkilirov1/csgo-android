#!/bin/bash
cd ~/csgo-src
A=/opt/android-ndk-r20b/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android-addr2line
$A -e build/vguimatsurface/libvguimatsurface.so -f -C 0x1382CC 0x138270 0x139234 0x29A39C 0x29A718 0x2997BC 0x298FAC 0x121F0C 0x121D38
