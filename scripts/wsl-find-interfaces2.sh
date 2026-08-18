#!/bin/bash
cd ~/csgo-src
# real version strings from headers, checked against all built .so
grep -rhoE '"[A-Za-z0-9]+[0-9]{2,3}"' build --include="*.so" >/dev/null 2>&1
for s in "VEngineModel016" "EngineTraceClient004" "VEngineStringTable001" "VEngineSpatialPartition001" "VEngineShadowMgr001" "VEngineStaticPropMgrClient002" "VEngineSound001" "VEngineGameEventManager002" "SoundEmitterSystem001" "VInputSystem001" "VSceneFileCache002" "VBlackBox001" "VXboxSystem001" "VEngineRenderToRTHelper001" "VEngineGameTypes001" "VEngineMatchFramework001"; do
  HITS=$(grep -rl "$s" build --include="*.so" 2>/dev/null | sed 's|build/||' | head -2 | tr '\n' ' ')
  echo "$s -> ${HITS:-<none>}"
done
