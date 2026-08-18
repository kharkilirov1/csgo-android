#!/bin/bash
cd ~/csgo-src
E=build/engine/libengine.so
for s in VEngineClient014 VEngineHudModel00 VEngineEffects001 VEngineTraceClient004 FileLoggingListener001 VEngineRenderView014 VDebugOverlay004 VDataCache003 VModelInfoClient004 VEngineVGui001 VEngineStringTable001 VEngineSpatialPartition001 VEngineShadowMgr001 VEngineStaticPropMgrClient002 VEngineSound001 VFileSystem017 VEngineRandom001 VEngineGameUIFuncs005 VEngineGameEventManager002 SoundEmitterSystem001 VInputSystem001 VSceneFileCache002 VBlackBox001 VXboxSystem001 VEngineRenderToRTHelper001 VEngineGameTypes001 VEngineMatchFramework001; do
  c=$(strings "$E" | grep -c "^$s$")
  echo "$c $s"
done
