#!/bin/bash
# Check diagnostics embedded in the built APK (run inside WSL).
cd "$HOME/csgo-src/android/csgo-launcher/app/build/outputs/apk/debug" || exit 1
unzip -p app-debug.apk lib/arm64-v8a/libvgui2.so > /tmp/vg3.so
unzip -p app-debug.apk lib/arm64-v8a/liblauncher.so > /tmp/la3.so
IDBG=$(strings /tmp/vg3.so | grep -c InputDBG)
CRASHH=$(strings /tmp/la3.so | grep -c "crash report begin")
REGS=$(strings /tmp/la3.so | grep -c "fp=0x")
echo "IDBG=$IDBG CRASHH=$CRASHH REGS=$REGS"
