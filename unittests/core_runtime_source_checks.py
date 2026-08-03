#!/usr/bin/env python3
"""Focused source-level regressions for Android runtime safety fixes.

These checks intentionally use only the Python standard library so they can be
run even when the native Android toolchain is unavailable.
"""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def source(relative_path: str) -> str:
    data = (ROOT / relative_path).read_bytes()
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin-1")


class CoreRuntimeSourceChecks(unittest.TestCase):
    def test_fast_quad_has_non_x86_copy(self) -> None:
        text = source("public/materialsystem/imesh.h")
        body = text.split("inline void CVertexBuilder::FastQuadVertexSSE", 1)[1]
        body = body.split("inline ", 1)[0]
        self.assertIn("#else", body)
        self.assertIn("m_VertexSize_Position < static_cast<int>( sizeof( vertex ) )", body)
        self.assertIn("memcpy( m_pCurrPosition, &vertex, sizeof( vertex ) )", body)

    def test_collision_set_checks_both_bounds_and_uses_unsigned_masks(self) -> None:
        text = source("vphysics/main.cpp")
        self.assertIn("index0 >= 0 && index0 < m_maxElementCount", text)
        self.assertIn("index1 >= 0 && index1 < m_maxElementCount", text)
        self.assertIn("1u << index1", text)
        self.assertIn("id == 0 || maxElementCount < 0 || maxElementCount > 32", text)

    def test_collision_pair_parser_rejects_signed_out_of_range_indices(self) -> None:
        text = source("vphysics/vcollide_parse.cpp")
        self.assertIn("j0 >= 0 && j0 < 32 && j1 >= 0 && j1 < 32", text)

    def test_vcollide_unload_releases_owned_user_data(self) -> None:
        text = source("vphysics/physics_collide.cpp")
        body = text.split("void CPhysicsCollision::VCollideUnload", 1)[1]
        body = body.split("IVPhysicsKeyParser *", 1)[0]
        self.assertLess(body.index("VCollideFreeUserData"), body.index("memset( pVCollide"))

    def test_alternate_gravity_uses_a_distinct_controller(self) -> None:
        environment = source("vphysics/physics_environment.cpp")
        physics_object = source("vphysics/physics_object.cpp")
        self.assertIn("new IVP_Standard_Gravity_Controller", environment)
        self.assertIn("m_pAlternateGravityController->set_standard_gravity", environment)
        self.assertIn("pDesiredGravity = m_useAlternateGravity", physics_object)
        self.assertIn("SetUseAlternateGravity( objectTemplate.useAlternateGravity )", physics_object)

    def test_unsupported_prediction_fails_closed(self) -> None:
        text = source("vphysics/physics_environment.cpp")
        body = text.split("void CPhysicsEnvironment::SetPredicted", 1)[1]
        body = body.split("bool CPhysicsEnvironment::IsPredicted", 1)[0]
        self.assertIn("m_bPredicted = false", body)
        self.assertIn("m_predictionCommandNum = 0", body)

    def test_android_squirrel_remote_debugger_is_compile_time_disabled(self) -> None:
        debugger = source("vscript/languages/squirrel/sqdbg/sqrdbg.cpp")
        vm = source("vscript/languages/squirrel/vsquirrel/vsquirrel.cpp")
        init_guard = debugger.split("HSQREMOTEDBG sq_rdbg_init", 1)[1].split("sockaddr_in", 1)[0]
        self.assertIn("!defined( __ANDROID__ )", init_guard)
        connect = vm.split("bool ConnectDebugger()", 1)[1].split("void DisconnectDebugger", 1)[0]
        self.assertIn("defined( __ANDROID__ )", connect)
        self.assertIn("return false", connect)

    def test_null_steam_creates_a_stable_offline_local_player(self) -> None:
        player = source("matchmaking/player.cpp")
        constructor = player.split("PlayerLocal::PlayerLocal", 1)[1].split("PlayerLocal::~PlayerLocal", 1)[0]
        self.assertIn("ISteamUser *pSteamUser", constructor)
        self.assertIn("m_xuid = 1ull", constructor)
        self.assertIn("m_eOnlineState = IPlayer::STATE_OFFLINE", constructor)
        self.assertIn("GetGuestPlayerName", constructor)
        self.assertIn("!steamIDPlayer.IsValid()", constructor)

        title_load = player.split("void PlayerLocal::LoadTitleData", 1)[1]
        title_load = title_load.split("static bool SetSteamStatWithPotentialOverride", 1)[0]
        self.assertIn('CreateEvent( "reset_game_titledata" )', title_load)
        self.assertIn('new KeyValues( "ResetConfiguration"', title_load)
        self.assertIn("OnProfileTitleDataLoaded( 0 )", title_load)

        logon = player.split("void PlayerLocal::UpdatePlayersSteamLogon", 1)[1]
        logon = logon.split("void PlayerLocal::Steam_OnServersConnected", 1)[0]
        self.assertIn("m_xuid == 1ull", logon)
        self.assertIn("cSteamId.IsValid()", logon)

        manager = source("matchmaking/playermanager.cpp")
        users_changed = manager.split("void PlayerManager::OnGameUsersChanged", 1)[1]
        users_changed = users_changed.split("void PlayerManager::RecomputePlayerXUIDs", 1)[0]
        self.assertNotIn("if ( !steamapicontext->SteamUser() )", users_changed)
        self.assertIn("new PlayerLocal( 0 )", users_changed)
        self.assertIn("steamapicontext && steamapicontext->SteamFriends()", users_changed)
        self.assertIn("EnableFriendsUpdate( bEnableFriendsUpdate )", users_changed)

    def test_missing_steam_session_services_are_offline_and_fail_closed(self) -> None:
        framework = source("matchmaking/mm_framework.cpp")
        services = framework.split("static bool MM_HasSteamSessionServices", 1)[1]
        services = services.split("void CMatchFramework::CreateSession", 1)[0]
        self.assertIn("SteamUser()", services)
        self.assertIn("SteamMatchmaking()", services)
        self.assertIn("SteamNetworking()", services)

        create = framework.split("void CMatchFramework::CreateSession", 1)[1]
        create = create.split("void CMatchFramework::MatchSession", 1)[0]
        self.assertIn('pSettings->SetString( "system/network", "offline" )', create)
        self.assertIn("CMatchSessionOfflineCustom", create)

        match = framework.split("void CMatchFramework::MatchSession", 1)[1]
        match = match.split("void CMatchFramework::CloseSession", 1)[0]
        offline = match.index('pSettings->SetString( "system/network", "offline" )')
        fail_closed = match.index("return;", offline)
        online_client = match.index("new CMatchSessionOnlineClient")
        self.assertLess(fail_closed, online_client)

    def test_dlc_info_is_lazy_non_null_and_steam_utils_are_guarded(self) -> None:
        dlc = source("matchmaking/mm_dlc.cpp")
        getter = dlc.split("KeyValues * CDlcManager::GetDataInfo", 1)[1]
        getter = getter.split("void CDlcManager::OnEvent", 1)[0]
        self.assertIn('new KeyValues( "DlcManager" )', getter)
        self.assertIn('SetUint64( "@info/installed", 0 )', getter)

        callback = dlc.split("void CDlcManager::Steam_OnDLCInstalled", 1)[1]
        self.assertLess(callback.index("GetDataInfo();"), callback.index("uiOldDlcMask"))
        self.assertIn("ISteamApps *pSteamApps", callback)
        self.assertIn("pSteamApps && pSteamApps->BIsSubscribedApp", callback)

        title = source("matchmaking/cstrike15/mm_title_gamesettingsmgr.cpp")
        self.assertIn("mm_sv_load_test.GetBool() && pSteamUtils", title)
        self.assertGreaterEqual(title.count("pFriends && pSteamUtils"), 2)
        update_keys = title.split("void CMatchTitleGameSettingsMgr::ExtendGameSettingsUpdateKeys", 1)[1]
        update_keys = update_keys.split("KeyValues *CMatchTitleGameSettingsMgr::ExtendTeamLobbyToGame", 1)[0]
        self.assertIn("pSteamFriends ? pSteamFriends->GetClanTag", update_keys)
        aggregate = title.split("void UpdateAggregateMembersSettings", 1)[1]
        aggregate = aggregate.split("void CMatchTitleGameSettingsMgr::ExecuteCommand", 1)[0]
        self.assertNotIn("static CSteamID", aggregate)
        self.assertIn("steamapicontext && steamapicontext->SteamUser()", aggregate)
        self.assertIn("mySteamID.IsValid() && playerSteamID.IsValid()", aggregate)

    def test_offline_voice_and_achievements_do_not_require_steam(self) -> None:
        voice = source("matchmaking/mm_voice.cpp")
        muted = voice.split("bool CMatchVoice::IsTalkerMuted", 1)[1]
        muted = muted.split("bool CMatchVoice::IsMachineMuted", 1)[0]
        self.assertIn("ISteamFriends *pSteamFriends", muted)
        self.assertGreaterEqual(muted.count("pSteamFriends && FriendRelationshipMute"), 2)
        self.assertIn("m_arrMutedTalkers.Find", muted)
        self.assertNotIn("steamapicontext->SteamFriends()->", muted)

        recording = voice.split("bool CMatchVoice::IsVoiceRecording", 1)[1]
        recording = recording.split("void CMatchVoice::SetVoiceRecording", 1)[0]
        self.assertIn("if ( !pSteamUser )", recording)
        self.assertIn("pSteamUser->GetAvailableVoice", recording)

        set_recording = voice.split("void CMatchVoice::SetVoiceRecording", 1)[1]
        set_recording = set_recording.split("void CMatchVoice::MuteTalker", 1)[0]
        self.assertIn("if ( !pSteamUser )", set_recording)
        self.assertIn("pSteamUser->StartVoiceRecording", set_recording)
        self.assertIn("pSteamUser->StopVoiceRecording", set_recording)

        player = source("matchmaking/player.cpp")
        awards = player.split("void PlayerLocal::UpdateAwardsData", 1)[1]
        awards = awards.split("void PlayerLocal::UpdatePendingAwardsState", 1)[0]
        self.assertIn("ISteamUserStats *pSteamUserStats", awards)
        self.assertIn("pSteamUserStats && pSteamUserStats->SetAchievement", awards)
        self.assertNotIn("steamapicontext->SteamUserStats()->SetAchievement", awards)

    def test_offline_leaderboards_fail_closed_without_queue_loops(self) -> None:
        player = source("matchmaking/player.cpp")
        read = player.split("void PlayerLocal::GetLeaderboardData", 1)[1]
        read = read.split("void PlayerLocal::UpdateLeaderboardData", 1)[0]
        self.assertIn("bCanQueryLeaderboard = steamapicontext && steamapicontext->SteamUserStats()", read)
        self.assertIn("bCanQueryLeaderboard &&", read)

        write = player.split("void PlayerLocal::UpdateLeaderboardData", 1)[1]
        write = write.split("void PlayerLocal::OnLeaderboardRequestFinished", 1)[0]
        self.assertIn("steamapicontext && steamapicontext->SteamUserStats()", write)

        queue = source("matchmaking/leaderboards.cpp")
        start = queue.split("void CLeaderboardRequestQueue::OnStartNewQuery", 1)[1]
        start = start.split("void CLeaderboardRequestQueue::OnSubmitQuery", 1)[0]
        self.assertIn("if ( !pSteamUserStats )", start)
        self.assertIn("Cleanup();", start)
        finished = queue.split("void CLeaderboardRequestQueue::OnQueryFinished", 1)[1]
        finished = finished.split("void CLeaderboardRequestQueue::Cleanup", 1)[0]
        self.assertIn("xuid && m_pFinishedRequest", finished)
        callbacks = queue.split("void CLeaderboardRequestQueue::Steam_OnLeaderboardFindResult", 1)[1]
        self.assertIn("!p || !pSteamUserStats", callbacks)
        self.assertNotIn("steamapicontext->SteamUserStats()->", callbacks)

        writer = source("matchmaking/steam_lobbyapi.cpp")
        entry = writer.split("void Steam_WriteLeaderboardData", 1)[1]
        self.assertIn("!pSteamUserStats || !pSteamUser", entry)
        self.assertIn("pViewDescription, pViewData, pSteamUserStats", entry)


if __name__ == "__main__":
    unittest.main()
