/*
Copyright (C) 2022 nillerusr

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of 
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
*/

#include <stdio.h>
#include <string.h>
#include <dlfcn.h>
#include <jni.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <SDL_hints.h>
#include "tier0/dbg.h"
#include "tier0/threadtools.h"

char *LauncherArgv[512];
char java_args[4096];
int iLastArgs = 0;

extern void InitCrashHandler();
DLL_EXPORT int LauncherMain( int argc, char **argv ); // from launcher.cpp

DLL_EXPORT int Java_com_valvesoftware_ValveActivity2_setenv(JNIEnv *jenv, jclass clazz, jstring env, jstring value, jint over)
{
	if ( !env || !value )
		return -1;

	const char *nameChars = jenv->GetStringUTFChars( env, NULL );
	const char *valueChars = jenv->GetStringUTFChars( value, NULL );
	if ( !nameChars || !valueChars )
	{
		if ( nameChars )
			jenv->ReleaseStringUTFChars( env, nameChars );
		if ( valueChars )
			jenv->ReleaseStringUTFChars( value, valueChars );
		return -1;
	}

	Msg( "Java environment: %s=<%u bytes>\n", nameChars, (unsigned)strlen( valueChars ) );
	int result = setenv( nameChars, valueChars, over );
	jenv->ReleaseStringUTFChars( env, nameChars );
	jenv->ReleaseStringUTFChars( value, valueChars );
	return result;
}

DLL_EXPORT void Java_com_valvesoftware_ValveActivity2_nativeOnActivityResult()
{
//	Msg( "Java_com_valvesoftware_ValveActivity_nativeOnActivityResult\n" );
}

DLL_EXPORT void Java_com_valvesoftware_ValveActivity2_setArgs(JNIEnv *env, jclass clazz, jstring str)
{
	java_args[0] = '\0';
	if ( !str )
		return;

	const char *args = env->GetStringUTFChars( str, NULL );
	if ( !args )
		return;

	strncpy( java_args, args, sizeof( java_args ) - 1 );
	java_args[sizeof( java_args ) - 1] = '\0';
	env->ReleaseStringUTFChars( str, args );
}

void SetLauncherArgs()
{
#define D(a) do { if ( iLastArgs < (int)( sizeof( LauncherArgv ) / sizeof( LauncherArgv[0] ) ) ) LauncherArgv[iLastArgs++] = (char*)a; } while ( 0 )
#define A(a,b) do { D(a); D(b); } while ( 0 )

	iLastArgs = 0;
	memset( LauncherArgv, 0, sizeof( LauncherArgv ) );

	static char binPath[2048];
	const char *appDataPath = getenv( "APP_DATA_PATH" );
	if ( !appDataPath || !appDataPath[0] )
		appDataPath = ".";
	snprintf(binPath, sizeof binPath, "%s/hl2_linux", appDataPath );
	D(binPath);

	const char *gamePath = getenv( "VALVE_GAME_PATH" );
	if ( gamePath && gamePath[0] )
		A( "-basedir", gamePath );

	D("-nouserclip");

	char *saveptr = NULL;
	char *pch = strtok_r( java_args, " ", &saveptr );
	while (pch != NULL)
	{
		D( pch );
		pch = strtok_r( NULL, " ", &saveptr );
	}

	D("-fullscreen");
	D("-nosteam");
	D("-insecure");

#undef A
#undef D
}

float GetTotalMemory()
{
	int64_t mem = 0;

	char meminfo[8196] = { 0 };
	FILE *f = fopen("/proc/meminfo", "r");
	if( !f )
		return 0.f;

	size_t size = fread(meminfo, 1, sizeof(meminfo), f);
	if( !size )
		return 0.f;

	char *s = strstr(meminfo, "MemTotal:");

	if( !s ) return 0.f;

	sscanf(s+9, "%lld", &mem);
	fclose(f);

	return mem/1024/1024.f;
}

void android_property_print(const char *name)
{
	char prop[1024];

	char strValue[64];
	memset (strValue, 0, 64);
	snprintf(prop, sizeof(prop), "getprop %s", name);
	FILE *fp = NULL;
	fp = popen(prop, "r");
	if (!fp) return;

	fgets(strValue, sizeof(strValue), fp);
	pclose(fp);
	fp = NULL;

	Msg("prop %s=%s", name, strValue);
}


DLL_EXPORT int LauncherMainAndroid( int argc, char **argv )
{
	InitCrashHandler();

	Msg("GetTotalMemory() = %.2f \n", GetTotalMemory());

	android_property_print("ro.build.version.sdk");
	android_property_print("ro.product.device");
	android_property_print("ro.product.manufacturer");
	android_property_print("ro.product.model");
	android_property_print("ro.product.name");

	SetLauncherArgs();

	const char *gamePath = getenv( "VALVE_GAME_PATH" );
	if ( gamePath && gamePath[0] && chdir( gamePath ) != 0 )
		Warning( "Unable to change working directory to selected game root '%s'.\n", gamePath );

	SDL_SetHint(SDL_HINT_TOUCH_MOUSE_EVENTS, "0");
	DeclareCurrentThreadIsMainThread(); // Init thread propertly on Android

	return LauncherMain(iLastArgs, LauncherArgv);
}
