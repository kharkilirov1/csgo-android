#!/bin/bash
cd ~/csgo-src
A=/opt/android-ndk-r20b/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android-addr2line
echo "===== vgui2 ====="
$A -e build/vgui2/src/libvgui2.so -f -C 0x61390 0x612DC 0x7BB94 0x7A9D4 0x79770 0x7C324 0xD0BA8 0x728B8
echo "===== client ====="
$A -e build/game/client/libclient.so -f -C 0x1BA1558 0x17570B8 0x1BA8CDC 0x1756DD4 0x696EAB8
echo "===== engine ====="
$A -e build/engine/libengine.so -f -C 0xBE2C04 0x8311D0 0x980818 0x98CFE8 0x987044 0xEFF578 0x985A98 0x985E34 0xA7C130 0xBDED94 0xE1B764 0x5F725C
echo "===== launcher ====="
$A -e build/launcher/liblauncher.so -f -C 0x569E8 0xAB044 0xC0588 0x57700 0x600C8
echo "===== vguimatsurface ====="
$A -e build/vguimatsurface/libvguimatsurface.so -f -C 0x122914
echo "===== inputsystem ====="
$A -e build/inputsystem/libinputsystem.so -f -C 0x560A4
