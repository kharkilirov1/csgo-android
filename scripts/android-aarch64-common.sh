#!/bin/sh

# Shared manifest for the Android arm64 build and APK packager. Keep dynamic
# modules here instead of duplicating incomplete lists across local scripts and
# CI. Waf builds the static dependencies of these targets automatically.

ANDROID_NDK_R20B_SHA256="8381c440fe61fcbb01e209211ac01b519cd6adf51ab1c2281d5daad6ca4c8c8c"

ANDROID_WAF_TARGETS="tier0,vstdlib,steam_api,togl,engine,matchmaking,filesystem_stdio,inputsystem,vphysics,materialsystem,datacache,studiorender,soundemittersystem,vscript,vguimatsurface,vgui2,scaleformui,shaderapidx9,stdshader_dx9,localize,scenefilecache,vaudio_minimp3,vaudio_opus,launcher,client,server"

ANDROID_REQUIRED_LIBRARIES="
libSDL2.so
libc++_shared.so
libtier0.so
libvstdlib.so
libsteam_api.so
libtogl.so
libengine.so
libmatchmaking.so
libfilesystem_stdio.so
libinputsystem.so
libvphysics.so
libmaterialsystem.so
libdatacache.so
libstudiorender.so
libsoundemittersystem.so
libvscript.so
libvguimatsurface.so
libvgui2.so
libscaleformui.so
libshaderapidx9.so
libstdshader_dx9.so
liblocalize.so
libscenefilecache.so
libvaudio_minimp3.so
libvaudio_opus.so
liblauncher.so
libclient.so
libserver.so
"

# Libraries supplied by Android itself rather than packaged in the APK.
ANDROID_SYSTEM_LIBRARIES="
libandroid.so
libatomic.so
libc.so
libdl.so
libEGL.so
libGLESv1_CM.so
libGLESv2.so
libjnigraphics.so
liblog.so
libm.so
libOpenSLES.so
libstdc++.so
libz.so
"

android_is_system_library()
{
	android_library=$1
	for android_system_library in $ANDROID_SYSTEM_LIBRARIES; do
		if [ "$android_library" = "$android_system_library" ]; then
			return 0
		fi
	done
	return 1
}

android_is_required_library()
{
	android_library=$1
	for android_required_library in $ANDROID_REQUIRED_LIBRARIES; do
		if [ "$android_library" = "$android_required_library" ]; then
			return 0
		fi
	done
	return 1
}
