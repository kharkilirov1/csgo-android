//========= Copyright Valve Corporation, All rights reserved. ============//
//
// Purpose: Native money readout.
//
//	CS:GO draws the account balance through Scaleform (sfhudmoney.cpp). That
//	backend is absent here, so this revives the VGUI element instead. It is the
//	Counter-Strike: Source implementation, moved into cstrike15 rather than
//	built from game/client/cstrike: a quoted include resolves against the
//	including file's own directory first, so compiling that file would pull in
//	CS:S's c_cs_player.h instead of this branch's.
//
//	The shared base (CHudBaseAccount) is already the CS:GO-era one.
//
//=============================================================================//

#include "cbase.h"
#include "hud_base_account.h"
#include "c_cs_player.h"
#include "clientmode_csnormal.h"

// memdbgon must be the last include file in a .cpp file!!!
#include "tier0/memdbgon.h"

using namespace vgui;

class CHudAccount : public CHudBaseAccount
{
public:
	DECLARE_CLASS_SIMPLE( CHudAccount, CHudBaseAccount );

	CHudAccount( const char *name );

	virtual bool ShouldDraw();
	virtual int	GetPlayerAccount( void );
	virtual vgui::AnimationController *GetAnimationController( void );
};

DECLARE_HUDELEMENT( CHudAccount );

CHudAccount::CHudAccount( const char *pName ) :
CHudBaseAccount( "HudAccount" )
{
	SetHiddenBits( HIDEHUD_PLAYERDEAD );
	SetIndent( false ); // don't indent small numbers in the drawing code - we're doing it manually
}

bool CHudAccount::ShouldDraw()
{
	C_CSPlayer *pPlayer = C_CSPlayer::GetLocalCSPlayer();
	if ( pPlayer )
	{
		return !pPlayer->IsObserver();
	}
	else
	{
		return false;
	}
}

// How much money does the player have
int	CHudAccount::GetPlayerAccount( void )
{
	C_CSPlayer *pPlayer = C_CSPlayer::GetLocalCSPlayer();

	if( !pPlayer )
		return 0;

	return (int)pPlayer->GetAccount();
}

vgui::AnimationController *CHudAccount::GetAnimationController( void )
{
	vgui::AnimationController *pController = GetClientModeCSNormal()->GetViewportAnimationController();

	Assert( pController );

	return pController;
}
