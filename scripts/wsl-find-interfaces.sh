#!/bin/bash
cd ~/csgo-src
DIR=build/android-libs 2>/dev/null || true
# use the jniLibs collected by build-apk if present, else engine dir
SEARCH_DIRS="build/android-libs build"
FOUND=""
for s in VEngineHudModel00 VEngineTraceClient004 VEngineStringTable001 VEngineSpatialPartition001 VEngineShadowMgr001 VEngineStaticPropMgrClient002 VEngineSound001 VEngineGameEventManager002 SoundEmitterSystem001 VInputSystem001 VSceneFileCache002 VBlackBox001 VXboxSystem001 VEngineRenderToRTHelper001 VEngineGameTypes001 VEngineMatchFramework001; do
  HITS=$(grep -rl "$s" build --include="*.so" 2>/dev/null | head -2 | tr '\n' ' ')
  echo "$s -> ${HITS:-<none>}"
done
