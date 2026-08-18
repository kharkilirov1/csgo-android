#!/usr/bin/env python3
"""Guard the Android legacy GameMenu label remap."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "game/client/cstrike15/gameui/BasePanel.cpp"

REMAPS = {
    "#GameUI_GameMenu_FindServers": "#SFUI_PlayMenu_BrowseServersButton",
    "#GameUI_GameMenu_CreateServer": "#SFUI_Start_ListenServer_Workshop_Map",
    "#GameUI_GameMenu_Options": "#SFUI_MainMenu_HelpButton",
    "#GameUI_GameMenu_Quit": "#SFUI_MainMenu_QuitGameButton",
}


def main() -> None:
    source = SOURCE.read_text(encoding="utf-8", errors="strict")
    start = source.index("CGameMenu *CBaseModPanel::RecursiveLoadGameMenu")
    end = source.index("void CBaseModPanel::UnlockInput", start)
    body = source[start:end]

    assert "#if defined( ANDROID )" in body
    assert body.index("const char *label") < body.index("menu->AddMenuItem")
    for legacy, csgo in REMAPS.items():
        assert legacy in body, legacy
        assert csgo in body, csgo

    print("PASS: Android GameMenu legacy labels map to available CS:GO localization tokens")


if __name__ == "__main__":
    main()
