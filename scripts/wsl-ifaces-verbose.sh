#!/bin/bash
cd ~/csgo-src
for f in build/inputsystem/libinputsystem.so build/engine/libengine.so build/game/client/libclient.so build/soundemittersystem/libsoundemittersystem.so; do
  [ -f "$f" ] || { echo "MISSING: $f"; continue; }
  echo "== $f"
  for s in VInputSystem001 SoundEmitterSystem001 VEngineSound001 VEngineGameTypes001 VEngineStringTable001 VEngineSpatialPartition001 VEngineShadowMgr001 VEngineStaticPropMgrClient002 VEngineGameEventManager002 VSceneFileCache002 VBlackBox001 VXboxSystem001 VEngineRenderToRTHelper001 VEngineMatchFramework001; do
    c=$(strings "$f" 2>/dev/null | grep -c "^$s$")
    [ "$c" -gt 0 ] && echo "  $s: $c"
  done
done
echo "== all .so present in build (name grep) =="
find build -name "*.so" | sed 's|build/||' | sort | head -40
