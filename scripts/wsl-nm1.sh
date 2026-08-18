#!/bin/bash
cd ~/csgo-src
/opt/android-ndk-r20b/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android-nm -n build/togles/libtogl.so 2>/dev/null | awk '$1 >= "000000000006C000" && $1 <= "000000000006D800"' | head -10
echo ===
/opt/android-ndk-r20b/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android-nm -n build/togles/libtogl.so 2>/dev/null | grep -iE "d3ddevice|g_pD3D|IDirect3DDevice9" | head -8
