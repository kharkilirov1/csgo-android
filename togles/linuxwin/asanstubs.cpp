// Android has no desktop display database (X11/Quartz), but the D3D-to-GL
// abstraction still queries one through GLMDisplayDB to enumerate video
// modes. The old stub returned "failure" from every query, so the engine
// could not find any mode and fell back to a 640x480 default while the
// window stayed at native size - the game rendered into a small corner.
// Expose the single current display mode through the launcher manager
// instead. Return convention follows the original GLMDisplayDB: true means
// the call failed.

typedef unsigned int   uint;

#include <string.h>

#include "../public/togles/linuxwin/glmdisplay.h"
#include "../public/togles/linuxwin/glmdisplaydb.h"
#include "../public/appframework/ilaunchermgr.h"

static bool GetCurrentDisplayModeFields( GLMDisplayModeInfoFields *infoOut )
{
	if ( !g_pLauncherMgr )
		return true;

	uint w = 0, h = 0, hz = 0;
	g_pLauncherMgr->GetNativeDisplayInfo( 0, w, h, hz );
	if ( w == 0 || h == 0 )
		return true;

	// the game is landscape-locked; report the long side as width so the
	// engine's mode lookup can match its saved resolution
	if ( h > w )
	{
		uint t = w; w = h; h = t;
	}

	static bool bPrinted = false;
	if ( !bPrinted )
	{
		bPrinted = true;
		printf( "GLDB: reporting display mode %ux%u@%u\n", w, h, hz );
	}

	infoOut->m_modePixelWidth = w;
	infoOut->m_modePixelHeight = h;
	infoOut->m_modeRefreshHz = hz > 0 ? hz : 60;
	return false;
}

static void FillRendererInfo( GLMRendererInfoFields *infoOut )
{
	if ( !infoOut )
		return;

	memset( infoOut, 0, sizeof( GLMRendererInfoFields ) );
	infoOut->m_fullscreen = 1;
	infoOut->m_accelerated = 1;
	infoOut->m_windowed = 1;
	infoOut->m_maxSamples = 4;
	infoOut->m_maxAniso = 8;
	infoOut->m_vidMemory = 1536 * 1024 * 1024;
	infoOut->m_texMemory = 1536 * 1024 * 1024;
}

static void FillDisplayInfo( GLMDisplayInfoFields *infoOut )
{
	if ( !infoOut )
		return;

	memset( infoOut, 0, sizeof( GLMDisplayInfoFields ) );
	GLMDisplayModeInfoFields modeInfo;
	if ( !GetCurrentDisplayModeFields( &modeInfo ) )
	{
		infoOut->m_displayPixelWidth = modeInfo.m_modePixelWidth;
		infoOut->m_displayPixelHeight = modeInfo.m_modePixelHeight;
	}
}

void GLMDisplayDB::PopulateRenderers( void ) { }
void GLMDisplayDB::PopulateFakeAdapters( uint realRendererIndex ) { }
void GLMDisplayDB::Populate( void ) { }
int	 GLMDisplayDB::GetFakeAdapterCount( void ) { return 1; }

bool GLMDisplayDB::GetFakeAdapterInfo( int fakeAdapterIndex, int *rendererOut, int *displayOut, GLMRendererInfoFields *rendererInfoOut, GLMDisplayInfoFields *displayInfoOut )
{
	if ( rendererOut ) *rendererOut = 0;
	if ( displayOut ) *displayOut = 0;
	FillRendererInfo( rendererInfoOut );
	FillDisplayInfo( displayInfoOut );
	return false;
}

int	 GLMDisplayDB::GetRendererCount( void ) { return 1; }

bool GLMDisplayDB::GetRendererInfo( int rendererIndex, GLMRendererInfoFields *infoOut )
{
	FillRendererInfo( infoOut );
	return false;
}

int	 GLMDisplayDB::GetDisplayCount( int rendererIndex ) { return 1; }

bool GLMDisplayDB::GetDisplayInfo( int rendererIndex, int displayIndex, GLMDisplayInfoFields *infoOut )
{
	FillDisplayInfo( infoOut );
	return false;
}

int	 GLMDisplayDB::GetModeCount( int rendererIndex, int displayIndex )
{
	// enumerate nothing: g_pLauncherMgr is not reachable from this library on
	// Android (it binds to a private NULL copy), so no mode can be reported;
	// the engine instead trusts the window size it was given
	return 0;
}

bool GLMDisplayDB::GetModeInfo( int rendererIndex, int displayIndex, int modeIndex, GLMDisplayModeInfoFields *infoOut )
{
	// modeIndex -1 asks for the display's current mode; 0 is the single
	// mode we enumerate
	if ( !infoOut || modeIndex > 0 )
		return true;

	return GetCurrentDisplayModeFields( infoOut );
}

void GLMDisplayDB::Dump( void ) { }
