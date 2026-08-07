//========= Copyright Valve Corporation, All rights reserved. ============//
//
// No-op implementation of the closed-source Steam Datagram transport
// library for platforms where it is unavailable (Android).
//
//=============================================================================//
#include "tier1/strtools.h"
#include "steamdatagram/isteamdatagramclient.h"
#include "steamdatagram/isteamdatagramserver.h"
#include "steamdatagram/isteamnetworkingutils.h"
#include "ixboxsystem.h"
#include "inputsystem/iinputstacksystem.h"

// memdbgon must be the last include file in a .cpp file!!!
#include "tier0/memdbgon.h"

void SteamDatagramClient_Init( const char *pszCacheDirectory, ESteamDatagramPartner ePartner, int iPartnerMask )
{
}

ISteamDatagramTransportClient *SteamDatagramClient_Connect( CSteamID steamID )
{
	return NULL;
}

void SteamDatagramClient_Kill()
{
}

ISteamDatagramTransportGameserver *SteamDatagram_GameserverListen( EUniverse eUniverse, uint16 unBindPort, EResult *pOutResult, SteamDatagramErrMsg &errMsg )
{
	if ( pOutResult )
		*pOutResult = k_EResultFail;
	V_strncpy( errMsg, "Steam datagram transport is not available on this platform", sizeof( SteamDatagramErrMsg ) );
	return NULL;
}

ISteamNetworkingUtils *SteamNetworkingUtils()
{
	return NULL;
}

int ISteamDatagramTransportClient::ConnectionStatus::Print( char *pszBuf, int cbBuf ) const
{
	if ( pszBuf && cbBuf > 0 )
		pszBuf[0] = '\0';
	return 0;
}

// g_pXboxSystem comes from xboxsystem.cpp (the PC-stub CXboxSystem), which
// server/client/gameui DLLInit all hard-require.

InputContextHandle_t GetGameInputContext()
{
	return INPUT_CONTEXT_HANDLE_INVALID;
}

// OpenAL capture and Steam Audio (phonon) libraries are not available on
// Android: voice capture reports no device, binaural init reports failure.
extern "C" {

void *alcCaptureOpenDevice( const char *pszName, unsigned int nFreq, int nFormat, int nBufSize ) { return NULL; }
char alcCaptureCloseDevice( void *pDevice ) { return 0; }
void alcCaptureStart( void *pDevice ) {}
void alcCaptureStop( void *pDevice ) {}
void alcCaptureSamples( void *pDevice, void *pBuffer, int nSamples ) {}
int alcGetError( void *pDevice ) { return 0; }
void alcGetIntegerv( void *pDevice, int nParam, int nSize, int *pValues ) { if ( pValues && nSize > 0 ) pValues[0] = 0; }

int iplCreate3DContext() { return 1; }
void iplDestroy3DContext() {}
int iplCreateBinauralRenderer() { return 1; }
void iplDestroyBinauralRenderer() {}
int iplCreateBinauralEffect() { return 1; }
void iplDestroyBinauralEffect() {}
void iplApplyBinauralEffect() {}

}
