//========= Copyright Valve Corporation, All rights reserved. ============//
//
// Purpose: A do-nothing IScaleformUI.
//
//	CS:GO drives its menus and HUD through Scaleform, which is Autodesk's
//	proprietary GFx Flash runtime. GFx is not part of this tree, was
//	discontinued, and never shipped for ARM64 - so there is nothing to link
//	against on Android.
//
//	Game code reaches Scaleform exclusively through the g_pScaleformUI /
//	ScaleformUI() interface pointer, which the launcher fills in from this
//	module's factory. Leaving it NULL means every sfhud_* call site
//	dereferences NULL; providing this stub makes them harmless no-ops
//	instead, so the game runs with the Flash UI simply absent. The native
//	VGUI HUD is what draws in its place.
//
//	Every method returns a benign default: no movies, no slots, no values.
//
//=============================================================================//

#include "tier1/convar.h"
#include "scaleformui/scaleformui.h"
#include "tier1/interface.h"

// memdbgon must be the last include file in a .cpp file!!!
#include "tier0/memdbgon.h"


class CScaleformUIStub : public IScaleformUI
{
public:
	// IAppSystem
	virtual bool Connect( CreateInterfaceFn factory ) { return true; }
	virtual void Disconnect() {}
	virtual void *QueryInterface( const char *pInterfaceName )
	{
		if ( pInterfaceName && !V_strcmp( pInterfaceName, SCALEFORMUI_INTERFACE_VERSION ) )
			return static_cast< IScaleformUI * >( this );
		return NULL;
	}
	virtual InitReturnVal_t Init() { return INIT_OK; }
	virtual void Shutdown() {}
	virtual AppSystemTier_t GetTier() { return APP_SYSTEM_TIER3; }

	// IScaleformUI - generated no-ops
	virtual void DumpMeshCacheStats(  )
	{
	}

	virtual void SetSingleThreadedMode( bool bSingleThreded )
	{
	}

	virtual void RunFrame( float time )
	{
	}

	virtual void AdvanceSlot( int slot )
	{
	}

	virtual bool HandleInputEvent( const InputEvent_t &event )
	{
		return false;
	}

	virtual bool HandleIMEEvent( size_t hwnd, unsigned int uMsg, unsigned int  wParam, long lParam )
	{
		return false;
	}

	virtual bool PreProcessKeyboardEvent( size_t hwnd, unsigned int uMsg, unsigned int  wParam, long lParam )
	{
		return false;
	}

	virtual void SetIMEEnabled( bool bEnabled )
	{
	}

	virtual void SetIMEFocus( int slot )
	{
	}

	virtual void ShutdownIME(  )
	{
	}

	virtual float GetJoyValue( int slot, int stickIndex, int axis )
	{
		return 0.0f;
	}

	virtual void SetSlotViewport( int slot, int x, int y, int width, int height )
	{
	}

	virtual void RenderSlot( int slot )
	{
	}

	virtual void ForkRenderSlot( int slot )
	{
	}

	virtual void JoinRenderSlot( int slot )
	{
	}

	virtual void InitSlot( int slotID, const char* rootMovie, IScaleformSlotInitController *pController )
	{
	}

	virtual void SlotRelease( int slotID )
	{
	}

	virtual void SlotAddRef( int slot )
	{
	}

	virtual void LockSlot( int slot )
	{
	}

	virtual void UnlockSlot( int slot )
	{
	}

	virtual void RequestElement( int slot, const char* elementName, ScaleformUIFunctionHandlerObject* object, const IScaleformUIFunctionHandlerDefinitionTable* tableObject )
	{
	}

	virtual void RemoveElement( int slot, SFVALUE element )
	{
	}

	virtual void InstallGlobalObject( int slot, const char* elementName, ScaleformUIFunctionHandlerObject* object, const IScaleformUIFunctionHandlerDefinitionTable* tableObject, SFVALUE *pInstalledGlobalObjectResult )
	{
		// No object was installed.  Do not leave an output handle containing
		// whatever happened to be on the caller's stack.
		if ( pInstalledGlobalObjectResult )
			*pInstalledGlobalObjectResult = NULL;
	}

	virtual void RemoveGlobalObject( int slot, SFVALUE element )
	{
	}

	virtual bool SlotConsumesInputEvents( int slot )
	{
		return false;
	}

	virtual bool ConsumesInputEvents( void )
	{
		return false;
	}

	virtual bool SlotDeniesInputToGame( int slot )
	{
		return false;
	}

	virtual void DenyInputToGame( bool value )
	{
	}

	virtual void DenyInputToGameFromFlash( int slot, bool value )
	{
	}

	virtual void LockInputToSlot( int slot )
	{
	}

	virtual void UnlockInput( void )
	{
	}

	virtual bool AvatarImageAddRef( uint64 playerID )
	{
		return false;
	}

	virtual void AvatarImageRelease( uint64 playerID )
	{
	}

	virtual void AvatarImageReload( uint64 playerID, IScaleformAvatarImageProvider *pProvider )
	{
	}

	virtual void AddDeviceDependentObject( IShaderDeviceDependentObject * pObject )
	{
	}

	virtual void RemoveDeviceDependentObject( IShaderDeviceDependentObject * pObject )
	{
	}

	virtual bool InventoryImageAddRef( uint64 iItemId, IScaleformInventoryImageProvider *pGlobalInventoryImageProvider )
	{
		return false;
	}

	virtual void InventoryImageUpdate( uint64 iItemId, IScaleformInventoryImageProvider *pGlobalInventoryImageProvider )
	{
	}

	virtual void InventoryImageRelease( uint64 iItemId )
	{
	}

	virtual void InitInventoryDefaultIcons( CUtlVector< const char * > *vecIconDefaultNames )
	{
	}

	virtual bool ChromeHTMLImageAddRef( uint64 imageID )
	{
		return false;
	}

	virtual void ChromeHTMLImageUpdate( uint64 imageID, const byte* rgba, int width, int height, ::ImageFormat format )
	{
	}

	virtual void ChromeHTMLImageRelease( uint64 imageID )
	{
	}

	virtual void ForceUpdateImages(  )
	{
	}

	virtual ButtonCode_t GetCurrentKey(  )
	{
		return BUTTON_CODE_INVALID;
	}

	virtual void SendUIEvent( const char* action, const char* eventData, int slot )
	{
	}

	virtual void InitCursor( const char* cursorMovie )
	{
	}

	virtual void ReleaseCursor( void )
	{
	}

	virtual bool IsCursorVisible( void )
	{
		return false;
	}

	virtual void RenderCursor( void )
	{
	}

	virtual void AdvanceCursor( void )
	{
	}

	virtual void SetCursorViewport( int x, int y, int width, int height )
	{
	}

	virtual void ShowCursor( void )
	{
	}

	virtual void HideCursor( void )
	{
	}

	virtual void PS3UseMoveCursor( void )
	{
	}

	virtual void PS3UseStandardCursor( void )
	{
	}

	virtual void PS3ForceCursorStart( void )
	{
	}

	virtual void PS3ForceCursorEnd( void )
	{
	}

	virtual void SetCursorShape( int shapeIndex )
	{
	}

	virtual void ForceCollectGarbage( int slot )
	{
	}

	virtual bool IsSetToControllerUI( int slot )
	{
		return false;
	}

	virtual void LockMostRecentInputDevice( int slot )
	{
	}

	virtual void ClearCache( void )
	{
	}

	virtual SFMOVIEDEF CreateMovieDef( const char* pfilename, unsigned int loadConstants, size_t memoryArena )
	{
		return SFMOVIEDEF();
	}

	virtual void ReleaseMovieDef( SFMOVIEDEF movieDef )
	{
	}

	virtual SFMOVIE MovieDef_CreateInstance( SFMOVIEDEF movieDef, bool initFirstFrame, size_t memoryArena )
	{
		return SFMOVIE();
	}

	virtual void ReleaseMovieView( SFMOVIE movieView )
	{
	}

	virtual void MovieView_Advance( SFMOVIE movieView, float time, unsigned int frameCatchUpCount )
	{
	}

	virtual void MovieView_SetBackgroundAlpha( SFMOVIE movieView, float alpha )
	{
	}

	virtual void MovieView_SetViewport( SFMOVIE movieView, int bufw, int bufh, int left, int top, int w, int h, unsigned int flags )
	{
	}

	virtual void MovieView_Display( SFMOVIE movieView )
	{
	}

	virtual void MovieView_SetViewScaleMode( SFMOVIE movieView, _ScaleModeType type )
	{
	}

	virtual _ScaleModeType MovieView_GetViewScaleMode( SFMOVIE movieView )
	{
		return SM_NoScale;
	}

	virtual void MovieView_SetViewAlignment( SFMOVIE movieView, _AlignType type )
	{
	}

	virtual _AlignType MovieView_GetViewAlignment( SFMOVIE movieView )
	{
		return Align_Center;
	}

	virtual SFVALUE MovieView_CreateObject( SFMOVIE movieView, const char* className, SFVALUEARRAY args, int numArgs )
	{
		return SFVALUE();
	}

	virtual SFVALUE MovieView_GetVariable( SFMOVIE movieView, const char* variablePath )
	{
		return SFVALUE();
	}

	virtual SFVALUE MovieView_CreateString( SFMOVIE movieView, const char *str )
	{
		return SFVALUE();
	}

	virtual SFVALUE MovieView_CreateStringW( SFMOVIE movieView, const wchar_t *str )
	{
		return SFVALUE();
	}

	virtual SFVALUE MovieView_CreateArray( SFMOVIE movieView, int size )
	{
		return SFVALUE();
	}

	virtual const wchar_t* Translate( const char *key, bool* pIsHTML )
	{
		if ( pIsHTML )
			*pIsHTML = false;

		// Translation requires the unavailable GFx/localization integration.
		return NULL;
	}

	virtual const wchar_t* ReplaceGlyphKeywordsWithHTML( const wchar_t* pin, int fontSize, bool bForceControllerGlyph )
	{
		// Glyph replacement is unsupported, but the wide input is already in
		// the return representation, so an unchanged string is a safe no-op.
		return pin;
	}

	virtual const wchar_t* ReplaceGlyphKeywordsWithHTML( const char* text, int fontSize, bool bForceControllerGlyph )
	{
		// The narrow overload would require owned conversion storage.  NULL
		// keeps that unsupported operation explicit instead of returning a
		// dangling temporary.
		return NULL;
	}

	virtual void MakeStringSafe( const wchar_t* stringin, OUT_Z_BYTECAP(outlength) wchar_t* stringout, int outlength )
	{
		if ( !stringout || outlength < static_cast< int >( sizeof( *stringout ) ) )
			return;

		const int nCapacity = outlength / static_cast< int >( sizeof( *stringout ) );
		if ( !stringin )
		{
			stringout[0] = L'\0';
			return;
		}

		// The HTML escaping implementation belongs to the unavailable GFx
		// backend.  Preserve the caller's text while still honoring the byte
		// capacity contract and always producing a terminated output string.
		if ( stringout != stringin )
		{
			int i = 0;
			for ( ; i < nCapacity - 1 && stringin[i] != L'\0'; ++i )
				stringout[i] = stringin[i];
			stringout[i] = L'\0';
		}
		else
		{
			stringout[nCapacity - 1] = L'\0';
		}
	}

	virtual void RefreshKeyBindings( void )
	{
	}

	virtual void ShowActionNameWhenActionIsNotBound( bool value )
	{
	}

	virtual void UpdateBindingForButton( ButtonCode_t bt, const char* pbinding )
	{
	}

	virtual bool MovieView_HitTest( SFMOVIE movieView, float x, float y, _HitTestType testCond, unsigned int controllerIdx )
	{
		return false;
	}

	virtual SFVALUE CreateValue( SFVALUE value )
	{
		return SFVALUE();
	}

	virtual SFVALUE CreateValue( int value )
	{
		return SFVALUE();
	}

	virtual SFVALUE CreateValue( float value )
	{
		return SFVALUE();
	}

	virtual SFVALUE CreateValue( bool value )
	{
		return SFVALUE();
	}

	virtual SFVALUE CreateValue( const char* value )
	{
		return SFVALUE();
	}

	virtual SFVALUE CreateValue( const wchar_t* value )
	{
		return SFVALUE();
	}

	virtual SFVALUE CreateNewObject( int slot )
	{
		return SFVALUE();
	}

	virtual SFVALUE CreateNewString( int slot, const char* value )
	{
		return SFVALUE();
	}

	virtual SFVALUE CreateNewString( int slot, const wchar_t* value )
	{
		return SFVALUE();
	}

	virtual SFVALUE CreateNewArray( int slot, int size )
	{
		return SFVALUE();
	}

	virtual void Value_SetValue( SFVALUE obj, SFVALUE value )
	{
	}

	virtual void Value_SetValue( SFVALUE obj, int value )
	{
	}

	virtual void Value_SetValue( SFVALUE obj, float value )
	{
	}

	virtual void Value_SetValue( SFVALUE obj, bool value )
	{
	}

	virtual void Value_SetValue( SFVALUE obj, const char* value )
	{
	}

	virtual void Value_SetValue( SFVALUE obj, const wchar_t* value )
	{
	}

	virtual void Value_SetColor( SFVALUE obj, int color )
	{
	}

	virtual void Value_SetColor( SFVALUE obj, float r, float g, float b, float a )
	{
	}

	virtual void Value_SetTint( SFVALUE obj, int color )
	{
	}

	virtual void Value_SetTint( SFVALUE obj, float r, float g, float b, float a )
	{
	}

	virtual void Value_SetColorTransform( SFVALUE obj, int colorMultiply, int colorAdd )
	{
	}

	virtual void Value_SetColorTransform( SFVALUE obj, float r, float g, float b, float a, int colorAdd )
	{
	}

	virtual void Value_SetArraySize( SFVALUE obj, int size )
	{
	}

	virtual int Value_GetArraySize( SFVALUE obj )
	{
		return 0;
	}

	virtual void Value_ClearArrayElements( SFVALUE obj )
	{
	}

	virtual void Value_RemoveArrayElement( SFVALUE obj, int index )
	{
	}

	virtual void Value_RemoveArrayElements( SFVALUE obj, int index, int count )
	{
	}

	virtual SFVALUE Value_GetArrayElement( SFVALUE obj, int index )
	{
		return SFVALUE();
	}

	virtual void Value_SetArrayElement( SFVALUE obj, int index, SFVALUE value )
	{
	}

	virtual void Value_SetArrayElement( SFVALUE obj, int index, int value )
	{
	}

	virtual void Value_SetArrayElement( SFVALUE obj, int index, float value )
	{
	}

	virtual void Value_SetArrayElement( SFVALUE obj, int index, bool value )
	{
	}

	virtual void Value_SetArrayElement( SFVALUE obj, int index, const char* value )
	{
	}

	virtual void Value_SetArrayElement( SFVALUE obj, int index, const wchar_t* value )
	{
	}

	virtual void Value_SetText( SFVALUE obj, const char* value )
	{
	}

	virtual void Value_SetText( SFVALUE obj, const wchar_t* value )
	{
	}

	virtual void Value_SetTextHTML( SFVALUE obj, const char* value )
	{
	}

	virtual void Value_SetTextHTML( SFVALUE obj, const wchar_t* value )
	{
	}

	virtual int Value_SetFormattedText( SFVALUE obj, const char* pFormat, ... )
	{
		return 0;
	}

	virtual void ReleaseValue( SFVALUE value )
	{
	}

	virtual void CreateValueArray( SFVALUEARRAY& valueArray, int length )
	{
		// A non-zero count with a NULL backing store would make operator[]
		// dereference an invalid handle.  Empty explicitly denotes unsupported.
		valueArray.SetValues( 0, NULL );
	}

	virtual SFVALUEARRAY CreateValueArray( int length )
	{
		return SFVALUEARRAY();
	}

	// Deprecated overloads (declared with a trailing comment in the header).
	virtual void ReleaseValueArray( SFVALUEARRAY& valueArray, int count )
	{
		valueArray.SetValues( 0, NULL );
	}

	virtual bool Value_InvokeWithoutReturn( SFVALUE obj, const char* methodName, const SFVALUEARRAY& args, int numArgs )
	{
		return false;
	}

	virtual SFVALUE Value_Invoke( SFVALUE obj, const char* methodName, const SFVALUEARRAY& args, int numArgs )
	{
		return NULL;
	}

	virtual void ReleaseValueArray( SFVALUEARRAY& valueArray )
	{
		valueArray.SetValues( 0, NULL );
	}

	virtual SFVALUE ValueArray_GetElement( SFVALUEARRAY, int index )
	{
		return SFVALUE();
	}

	virtual _ValueType ValueArray_GetType( SFVALUEARRAY array, int index )
	{
		return IUIMarshalHelper::VT_Undefined;
	}

	virtual double ValueArray_GetNumber( SFVALUEARRAY array, int index )
	{
		return 0.0;
	}

	virtual bool ValueArray_GetBool( SFVALUEARRAY array, int index )
	{
		return false;
	}

	virtual const char* ValueArray_GetString( SFVALUEARRAY array, int index )
	{
		return NULL;
	}

	virtual const wchar_t* ValueArray_GetStringW( SFVALUEARRAY array, int index )
	{
		return NULL;
	}

	virtual void ValueArray_SetElement( SFVALUEARRAY, int index, SFVALUE value )
	{
	}

	virtual void ValueArray_SetElement( SFVALUEARRAY, int index, int value )
	{
	}

	virtual void ValueArray_SetElement( SFVALUEARRAY, int index, float value )
	{
	}

	virtual void ValueArray_SetElement( SFVALUEARRAY, int index, bool value )
	{
	}

	virtual void ValueArray_SetElement( SFVALUEARRAY, int index, const char* value )
	{
	}

	virtual void ValueArray_SetElement( SFVALUEARRAY, int index, const wchar_t* value )
	{
	}

	virtual void ValueArray_SetElementText( SFVALUEARRAY, int index, const char* value )
	{
	}

	virtual void ValueArray_SetElementText( SFVALUEARRAY, int index, const wchar_t* value )
	{
	}

	virtual void ValueArray_SetElementTextHTML( SFVALUEARRAY, int index, const char* value )
	{
	}

	virtual void ValueArray_SetElementTextHTML( SFVALUEARRAY, int index, const wchar_t* value )
	{
	}

	virtual bool Value_HasMember( SFVALUE value, const char* name )
	{
		return false;
	}

	virtual SFVALUE Value_GetMember( SFVALUE value, const char* name )
	{
		return SFVALUE();
	}

	virtual bool Value_SetMember( SFVALUE obj, const char *name, SFVALUE value )
	{
		return false;
	}

	virtual bool Value_SetMember( SFVALUE obj, const char *name, int value )
	{
		return false;
	}

	virtual bool Value_SetMember( SFVALUE obj, const char *name, float value )
	{
		return false;
	}

	virtual bool Value_SetMember( SFVALUE obj, const char *name, bool value )
	{
		return false;
	}

	virtual bool Value_SetMember( SFVALUE obj, const char *name, const char* value )
	{
		return false;
	}

	virtual bool Value_SetMember( SFVALUE obj, const char *name, const wchar_t* value )
	{
		return false;
	}

	virtual ISFTextObject* TextObject_MakeTextObject( SFVALUE value )
	{
		return NULL;
	}

	virtual ISFTextObject* TextObject_MakeTextObjectFromMember( SFVALUE value, const char* pName )
	{
		return NULL;
	}

	virtual bool Value_InvokeWithoutReturn( SFVALUE obj, const char* methodName, const SFVALUEARRAY& args )
	{
		return false;
	}

	virtual SFVALUE Value_Invoke( SFVALUE obj, const char* methodName, const SFVALUEARRAY& args )
	{
		return SFVALUE();
	}

	virtual bool Value_InvokeWithoutReturn( SFVALUE obj, const char* methodName, SFVALUE args, int numArgs )
	{
		return false;
	}

	virtual SFVALUE Value_Invoke( SFVALUE obj, const char* methodName, SFVALUE args, int numArgs )
	{
		return SFVALUE();
	}

	virtual void Value_SetVisible( SFVALUE obj, bool visible )
	{
	}

	virtual void Value_GetDisplayInfo( SFVALUE obj, ScaleformDisplayInfo* dinfo )
	{
		if ( dinfo )
		{
			// Several callers read these fields directly without consulting the
			// set flags.  Populate every value so the unsupported object is
			// deterministically invisible rather than exposing uninitialized data.
			dinfo->Clear();
			dinfo->SetX( 0.0 );
			dinfo->SetY( 0.0 );
			dinfo->SetRotation( 0.0 );
			dinfo->SetAlpha( 0.0 );
			dinfo->SetVisibility( false );
			dinfo->SetXScale( 100.0 );
			dinfo->SetYScale( 100.0 );
		}
	}

	virtual void Value_SetDisplayInfo( SFVALUE obj, const ScaleformDisplayInfo* dinfo )
	{
	}

	virtual _ValueType Value_GetType( SFVALUE obj )
	{
		return IUIMarshalHelper::VT_Undefined;
	}

	virtual double Value_GetNumber( SFVALUE obj )
	{
		return 0.0;
	}

	virtual bool Value_GetBool( SFVALUE obj )
	{
		return false;
	}

	virtual const char* Value_GetString( SFVALUE obj )
	{
		return NULL;
	}

	virtual const wchar_t* Value_GetStringW( SFVALUE obj )
	{
		return NULL;
	}

	virtual SFVALUE Value_GetText( SFVALUE obj )
	{
		return SFVALUE();
	}

	virtual SFVALUE Value_GetTextHTML( SFVALUE obj )
	{
		return SFVALUE();
	}


	// IUIMarshalHelper - generated no-ops
	virtual SFVALUEARRAY Params_GetArgs( SFPARAMS params )
	{
		return SFVALUEARRAY();
	}

	virtual unsigned int Params_GetNumArgs( SFPARAMS params )
	{
		return 0;
	}

	virtual bool Params_ArgIs( SFPARAMS params, unsigned int index, _ValueType v )
	{
		return false;
	}

	virtual SFVALUE Params_GetArg( SFPARAMS params, int index )
	{
		return SFVALUE();
	}

	virtual _ValueType Params_GetArgType( SFPARAMS params, int index )
	{
		return VT_Undefined;
	}

	virtual double Params_GetArgAsNumber( SFPARAMS params, int index )
	{
		return 0.0;
	}

	virtual bool Params_GetArgAsBool( SFPARAMS params, int index )
	{
		return false;
	}

	virtual const char* Params_GetArgAsString( SFPARAMS params, int index )
	{
		return NULL;
	}

	virtual const wchar_t* Params_GetArgAsStringW( SFPARAMS params, int index )
	{
		return NULL;
	}

	virtual void Params_DebugSpew( SFPARAMS params )
	{
	}

	virtual void Params_SetResult( SFPARAMS params, SFVALUE value )
	{
	}

	virtual void Params_SetResult( SFPARAMS params, int value )
	{
	}

	virtual void Params_SetResult( SFPARAMS params, float value )
	{
	}

	virtual void Params_SetResult( SFPARAMS params, bool value )
	{
	}

	virtual void Params_SetResult( SFPARAMS params, const char* value, bool bMakeNewValue )
	{
	}

	virtual void Params_SetResult( SFPARAMS params, const wchar_t* value, bool bMakeNewValue )
	{
	}

	virtual SFVALUE Params_CreateNewObject( SFPARAMS params )
	{
		return SFVALUE();
	}

	virtual SFVALUE Params_CreateNewString( SFPARAMS params, const char* value )
	{
		return SFVALUE();
	}

	virtual SFVALUE Params_CreateNewString( SFPARAMS params, const wchar_t* value )
	{
		return SFVALUE();
	}

	virtual SFVALUE Params_CreateNewArray( SFPARAMS params, int size )
	{
		return SFVALUE();
	}

};

static CScaleformUIStub g_ScaleformUIStub;
IScaleformUI *g_pScaleformUIStub = &g_ScaleformUIStub;

EXPOSE_SINGLE_INTERFACE_GLOBALVAR( CScaleformUIStub, IScaleformUI,
	SCALEFORMUI_INTERFACE_VERSION, g_ScaleformUIStub );
