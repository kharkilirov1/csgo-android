#!/usr/bin/env python3
import pathlib
import unittest
import xml.etree.ElementTree as ET


ROOT = pathlib.Path(__file__).resolve().parents[3]
LAUNCHER = ROOT / "android" / "csgo-launcher"
ANDROID_NS = "{http://schemas.android.com/apk/res/android}"


class LauncherIntegrationContractTest(unittest.TestCase):
    def read(self, relative_path):
        return (ROOT / relative_path).read_text(encoding="utf-8")

    def test_manifest_splits_legacy_and_modern_storage_access(self):
        manifest = ET.parse(LAUNCHER / "AndroidManifest.xml").getroot()
        permissions = {
            node.attrib[ANDROID_NS + "name"]: node
            for node in manifest.findall("uses-permission")
        }
        self.assertIn("android.permission.MANAGE_EXTERNAL_STORAGE", permissions)
        legacy = permissions["android.permission.WRITE_EXTERNAL_STORAGE"]
        self.assertEqual("29", legacy.attrib[ANDROID_NS + "maxSdkVersion"])

        features = {
            node.attrib[ANDROID_NS + "name"]: node
            for node in manifest.findall("uses-feature")
            if ANDROID_NS + "name" in node.attrib
        }
        for optional_hardware in (
            "android.hardware.microphone",
            "android.hardware.touchscreen",
            "android.hardware.wifi",
        ):
            self.assertEqual(
                "false", features[optional_hardware].attrib[ANDROID_NS + "required"]
            )

        gles = next(
            node
            for node in manifest.findall("uses-feature")
            if ANDROID_NS + "glEsVersion" in node.attrib
        )
        self.assertEqual("0x00030002", gles.attrib[ANDROID_NS + "glEsVersion"])
        self.assertEqual("true", gles.attrib[ANDROID_NS + "required"])

        application = manifest.find("application")
        activities = {
            node.attrib[ANDROID_NS + "name"]: node
            for node in application.findall("activity")
        }
        self.assertEqual(
            "false",
            activities["me.nillerusr.LauncherActivity"].attrib[
                ANDROID_NS + "hardwareAccelerated"
            ],
        )
        self.assertNotIn(
            ANDROID_NS + "hardwareAccelerated",
            activities["org.libsdl.app.SDLActivity"].attrib,
        )

    def test_android_requests_the_gles_version_required_by_togles(self):
        sdl_manager = self.read("appframework/sdlmgr.cpp")
        init = sdl_manager[sdl_manager.index("InitReturnVal_t CSDLMgr::Init()") :]
        init = init[: init.index("bool CSDLMgr::Connect")]

        profile = (
            "SET_GL_ATTR(SDL_GL_CONTEXT_PROFILE_MASK, "
            "SDL_GL_CONTEXT_PROFILE_ES);"
        )
        major = "SET_GL_ATTR(SDL_GL_CONTEXT_MAJOR_VERSION, 3);"
        minor = "SET_GL_ATTR(SDL_GL_CONTEXT_MINOR_VERSION, 2);"
        for attribute in (profile, major, minor):
            self.assertIn(attribute, init)
            self.assertLess(init.index(attribute), init.index("CreateHiddenGameWindow"))

    def test_selected_path_crosses_java_jni_and_filesystem_boundaries(self):
        activity = self.read("android/csgo-launcher/src/me/nillerusr/LauncherActivity.java")
        bridge = self.read("android/csgo-launcher/src/com/valvesoftware/ValveActivity2.java")
        native = self.read("launcher/android/main.cpp")
        filesystem = self.read("public/filesystem_init.cpp")

        self.assertIn("ValveActivity2.EXTRA_GAME_PATH", activity)
        self.assertIn('setenv("VALVE_GAME_PATH", gameRoot, 1)', bridge)
        self.assertIn('getenv( "VALVE_GAME_PATH" )', native)
        self.assertIn('A( "-basedir", gamePath )', native)
        self.assertIn("chdir( gamePath )", native)
        self.assertIn('getenv( "VALVE_GAME_PATH" )', filesystem)

    def test_environment_and_bundled_vpk_have_native_consumers(self):
        bridge = self.read("android/csgo-launcher/src/com/valvesoftware/ValveActivity2.java")
        extractor = self.read("android/csgo-launcher/src/me/nillerusr/ExtractAssets.java")
        sdl = self.read("android/csgo-launcher/src/org/libsdl/app/SDLActivity.java")
        launcher = self.read("launcher/launcher.cpp")

        self.assertIn("LauncherEnvironment.parse(specification)", bridge)
        self.assertIn('setenv("EXTRAS_VPK_PATH", joinedVPKs, 1)', bridge)
        self.assertIn(
            "#if defined( SUPPORT_VPK ) || defined( __ANDROID__ )", launcher
        )
        self.assertIn('getenv( "EXTRAS_VPK_PATH" )', launcher)
        self.assertIn("AddVPKFile( vpkPaths[i], PATH_ADD_TO_HEAD )", launcher)
        self.assertIn("isValidVPK(File file)", extractor)
        self.assertIn("prepareBundledExtras(context, intent)", bridge)
        self.assertIn("if (!ValveActivity2.initNatives(this, intent))", sdl)
        self.assertIn("showStartupError(ValveActivity2.getStartupErrorResource", sdl)

        bundled_vpk = (LAUNCHER / "assets" / "extras_dir.vpk").read_bytes()
        self.assertGreater(len(bundled_vpk), 4)
        self.assertEqual(b"\x34\x12\xaa\x55", bundled_vpk[:4])

    def test_sdl_activity_no_longer_blocks_on_obsolete_storage_permission(self):
        sdl = self.read("android/csgo-launcher/src/org/libsdl/app/SDLActivity.java")
        on_create = sdl[sdl.index("protected void onCreate(Bundle savedInstanceState)"):]
        on_create = on_create[:on_create.index("protected void pauseNativeThread")]
        self.assertIn("init();", on_create)
        self.assertNotIn("WRITE_EXTERNAL_STORAGE", on_create)

    def test_sdl_runtime_permission_result_reaches_native_waiter(self):
        sdl = self.read("android/csgo-launcher/src/org/libsdl/app/SDLActivity.java")
        callback = sdl[sdl.index("public void onRequestPermissionsResult("):]
        callback = callback[:callback.index("public static int openURL")]

        self.assertIn("super.onRequestPermissionsResult", callback)
        self.assertIn("grantResults.length > 0", callback)
        self.assertIn("PackageManager.PERMISSION_GRANTED", callback)
        self.assertIn("SDLActivity.nativePermissionResult(requestCode, granted)", callback)

    def test_android_modules_load_only_from_the_apk_native_directory(self):
        loader = self.read("tier1/interface.cpp")
        android_branch = loader[loader.index("#if defined( __ANDROID__ )"):]
        android_branch = android_branch[:android_branch.index("#else")]

        self.assertIn('getenv( "APP_LIB_PATH" )', android_branch)
        self.assertIn("V_FileBase( pModuleName", android_branch)
        self.assertIn('"lib%s%s"', android_branch)
        self.assertIn("Sys_LoadLibraryGuts( absoluteModuleName )", android_branch)
        self.assertNotIn("Sys_LoadLibraryGuts( pModuleName )", android_branch)


if __name__ == "__main__":
    unittest.main()
