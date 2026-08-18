#!/bin/bash
cd ~/csgo-src
echo "== search real interface version strings across all built .so =="
for s in "InputSystemVersion001" "VSoundEmitter003" "IEngineSoundClient003" "VEngineShadowMgr002" "StaticPropMgrClient005" "GAMEEVENTSMANAGER002" "BlackBoxVersion001" "VENGINE_GAMETYPES_VERSION002" "VEngineClientStringTable001" "SceneFileCache002" "XboxSystemInterface002" "RenderToRTHelper001" "SpatialPartition001" "MATCHFRAMEWORK_001" "VEngineModel016" "EngineTraceClient004" "VFileSystem017" "VEngineClient014" "VEngineRenderView014" "VEngineEffects001" "FileLoggingListener001" "VDebugOverlay004" "VDataCache003" "VModelInfoClient004" "VEngineVGui001" "VEngineRandom001"; do
  HITS=$(grep -rl "$s" build --include="*.so" 2>/dev/null | sed 's|build/||;s|/lib|/|' | tr '\n' ' ')
  echo "$s -> ${HITS:-<none>}"
done
