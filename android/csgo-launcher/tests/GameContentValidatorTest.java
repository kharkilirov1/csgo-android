package com.valvesoftware;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.RandomAccessFile;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.zip.CRC32;

public final class GameContentValidatorTest {
	private static final int VPK_SIGNATURE = 0x55AA1234;
	private static final int VPK_INLINE_ARCHIVE = 0x7FFF;
	private static final String REFERENCE_SET_SHA256 =
		"3d0463a142e614a1cd79cde97b470e538ea111bc2a11501a925b86306ae6051e";
	private static final String[] REFERENCE_WEAPONS = {
		"weapon_ak47", "weapon_aug", "weapon_awp", "weapon_bizon", "weapon_c4",
		"weapon_deagle", "weapon_decoy", "weapon_elite", "weapon_famas",
		"weapon_fiveseven", "weapon_flashbang", "weapon_g3sg1", "weapon_galilar",
		"weapon_glock", "weapon_healthshot", "weapon_hegrenade", "weapon_hkp2000",
		"weapon_incgrenade", "weapon_knife", "weapon_knifegg", "weapon_m249",
		"weapon_m4a1", "weapon_mac10", "weapon_mag7", "weapon_molotov",
		"weapon_mp7", "weapon_mp9", "weapon_negev", "weapon_nova", "weapon_p250",
		"weapon_p90", "weapon_sawedoff", "weapon_scar20", "weapon_sg556",
		"weapon_smokegrenade", "weapon_ssg08", "weapon_tagrenade", "weapon_taser",
		"weapon_tec9", "weapon_ump45", "weapon_xm1014"
	};

	private static final class TestEntry {
		final String path;
		final byte[] data;
		final boolean external;

		TestEntry(String path, String data, boolean external) {
			this.path = path;
			this.data = data.getBytes(StandardCharsets.UTF_8);
			this.external = external;
		}
	}

	private static void assertStatus(GameContentValidator.Status expected,
		GameContentValidator.Result actual) {
		if (actual.getStatus() != expected) {
			throw new AssertionError("Expected " + expected + ", got " +
				actual.getStatus() + ": " + actual.getDiagnostic());
		}
	}

	private static void writeText(File file, String value) throws Exception {
		File parent = file.getParentFile();
		if (!parent.isDirectory() && !parent.mkdirs())
			throw new IllegalStateException("Could not create " + parent);
		Files.write(file.toPath(), value.getBytes(StandardCharsets.UTF_8));
	}

	private static String manifest(String... names) {
		StringBuilder output = new StringBuilder("weapon_manifest\n{\n");
		for (String name : names)
			output.append("  \"file\" \"").append(name).append("\"\n");
		return output.append("}\n").toString();
	}

	private static void writeLooseContent(File mod, List<String> names,
		String omittedScript) throws Exception {
		writeText(new File(mod, "scripts/weapon_manifest.txt"),
			manifest(names.toArray(new String[names.size()])));
		for (String name : names) {
			if (!name.equals(omittedScript))
				writeText(new File(mod, "scripts/" + name + ".txt"), weaponScript(name));
		}
	}

	private static String weaponScript(String name) {
		return "WeaponData\n{\n  \"ClassName\" \"" + name + "\"\n}\n";
	}

	private static void writeU16(ByteArrayOutputStream output, int value) {
		output.write(value & 0xff);
		output.write((value >>> 8) & 0xff);
	}

	private static void writeU32(ByteArrayOutputStream output, long value) {
		output.write((int)(value & 0xff));
		output.write((int)((value >>> 8) & 0xff));
		output.write((int)((value >>> 16) & 0xff));
		output.write((int)((value >>> 24) & 0xff));
	}

	private static void writeString(ByteArrayOutputStream output, String value) {
		byte[] encoded = value.getBytes(StandardCharsets.ISO_8859_1);
		output.write(encoded, 0, encoded.length);
		output.write(0);
	}

	private static void writeVpk(File directory, int version,
		TestEntry... sourceEntries) throws Exception {
		writeVpk(directory, "pak01", version, sourceEntries);
	}

	private static void writeVpk(File directory, String baseName, int version,
		TestEntry... sourceEntries) throws Exception {
		List<TestEntry> entries = new ArrayList<TestEntry>(Arrays.asList(sourceEntries));
		Collections.sort(entries, new Comparator<TestEntry>() {
			@Override
			public int compare(TestEntry left, TestEntry right) {
				return left.path.compareTo(right.path);
			}
		});

		Map<String, List<TestEntry>> byExtension = new LinkedHashMap<String, List<TestEntry>>();
		for (TestEntry entry : entries) {
			int dot = entry.path.lastIndexOf('.');
			String extension = entry.path.substring(dot + 1);
			List<TestEntry> group = byExtension.get(extension);
			if (group == null) {
				group = new ArrayList<TestEntry>();
				byExtension.put(extension, group);
			}
			group.add(entry);
		}

		ByteArrayOutputStream tree = new ByteArrayOutputStream();
		ByteArrayOutputStream inlineData = new ByteArrayOutputStream();
		ByteArrayOutputStream externalData = new ByteArrayOutputStream();
		for (Map.Entry<String, List<TestEntry>> extensionGroup : byExtension.entrySet()) {
			writeString(tree, extensionGroup.getKey());
			Map<String, List<TestEntry>> byDirectory = new LinkedHashMap<String, List<TestEntry>>();
			for (TestEntry entry : extensionGroup.getValue()) {
				int slash = entry.path.lastIndexOf('/');
				String path = slash < 0 ? " " : entry.path.substring(0, slash);
				List<TestEntry> group = byDirectory.get(path);
				if (group == null) {
					group = new ArrayList<TestEntry>();
					byDirectory.put(path, group);
				}
				group.add(entry);
			}

			for (Map.Entry<String, List<TestEntry>> directoryGroup : byDirectory.entrySet()) {
				writeString(tree, directoryGroup.getKey());
				for (TestEntry entry : directoryGroup.getValue()) {
					int slash = entry.path.lastIndexOf('/');
					int dot = entry.path.lastIndexOf('.');
					writeString(tree, entry.path.substring(slash + 1, dot));
					CRC32 crc = new CRC32();
					crc.update(entry.data);
					writeU32(tree, crc.getValue());
					writeU16(tree, 0);
					writeU16(tree, entry.external ? 0 : VPK_INLINE_ARCHIVE);
					ByteArrayOutputStream destination = entry.external ? externalData : inlineData;
					writeU32(tree, destination.size());
					writeU32(tree, entry.data.length);
					writeU16(tree, 0xFFFF);
					destination.write(entry.data);
				}
				tree.write(0);
			}
			tree.write(0);
		}
		tree.write(0);

		File directoryVpk = new File(directory, baseName + "_dir.vpk");
		try (FileOutputStream output = new FileOutputStream(directoryVpk)) {
			ByteArrayOutputStream header = new ByteArrayOutputStream();
			writeU32(header, VPK_SIGNATURE);
			writeU32(header, version);
			writeU32(header, tree.size());
			if (version == 2) {
				writeU32(header, inlineData.size());
				writeU32(header, 0);
				writeU32(header, 0);
				writeU32(header, 0);
			}
			output.write(header.toByteArray());
			output.write(tree.toByteArray());
			output.write(inlineData.toByteArray());
		}
		if (externalData.size() > 0) {
			try (FileOutputStream output = new FileOutputStream(
				new File(directory, baseName + "_000.vpk"))) {
				output.write(externalData.toByteArray());
			}
		}
	}

	private static List<TestEntry> completeVpkEntries(String manifestText) {
		List<TestEntry> entries = new ArrayList<TestEntry>();
		entries.add(new TestEntry("scripts/weapon_manifest.txt", manifestText, false));
		for (String name : REFERENCE_WEAPONS)
			entries.add(new TestEntry("scripts/" + name + ".txt", weaponScript(name), false));
		return entries;
	}

	private static void patchU32(File file, long offset, long value) throws Exception {
		try (RandomAccessFile output = new RandomAccessFile(file, "rw")) {
			output.seek(offset);
			output.write((int)(value & 0xff));
			output.write((int)((value >>> 8) & 0xff));
			output.write((int)((value >>> 16) & 0xff));
			output.write((int)((value >>> 24) & 0xff));
		}
	}

	private static void patchFirstVpkArchiveIndex(File file, int value) throws Exception {
		byte[] bytes = Files.readAllBytes(file.toPath());
		int cursor = 28;
		for (int field = 0; field < 3; ++field) {
			while (cursor < bytes.length && bytes[cursor] != 0)
				++cursor;
			if (cursor >= bytes.length)
				throw new AssertionError("Could not locate first VPK entry");
			++cursor;
		}
		long archiveIndexOffset = cursor + 4 + 2;
		try (RandomAccessFile output = new RandomAccessFile(file, "rw")) {
			output.seek(archiveIndexOffset);
			output.write(value & 0xff);
			output.write((value >>> 8) & 0xff);
		}
	}

	private static long readU32(byte[] input, int offset) {
		return (input[offset] & 0xffL) |
			((input[offset + 1] & 0xffL) << 8) |
			((input[offset + 2] & 0xffL) << 16) |
			((input[offset + 3] & 0xffL) << 24);
	}

	private static byte[] shadowDirectoryGroup(String directory, String stem)
		throws Exception {
		byte[] preload = (directory + "/" + stem).getBytes(StandardCharsets.UTF_8);
		CRC32 crc = new CRC32();
		crc.update(preload);
		ByteArrayOutputStream group = new ByteArrayOutputStream();
		writeString(group, directory);
		writeString(group, stem);
		writeU32(group, crc.getValue());
		writeU16(group, preload.length);
		writeU16(group, VPK_INLINE_ARCHIVE);
		writeU32(group, 0);
		writeU32(group, 0);
		writeU16(group, 0xFFFF);
		group.write(preload);
		group.write(0);
		return group.toByteArray();
	}

	private static byte[] shadowExtensionGroup(String extension,
		String directory, String stem) throws Exception {
		ByteArrayOutputStream group = new ByteArrayOutputStream();
		writeString(group, extension);
		group.write(shadowDirectoryGroup(directory, stem));
		group.write(0);
		return group.toByteArray();
	}

	private static void insertBeforeVpkTreeTail(File vpk, int tailBytes,
		byte[] insertion) throws Exception {
		byte[] original = Files.readAllBytes(vpk.toPath());
		int version = (int)readU32(original, 4);
		int headerSize = version == 2 ? 28 : 12;
		int treeSize = (int)readU32(original, 8);
		int insertionOffset = headerSize + treeSize - tailBytes;
		ByteArrayOutputStream rewritten = new ByteArrayOutputStream(
			original.length + insertion.length);
		rewritten.write(original, 0, 8);
		writeU32(rewritten, treeSize + insertion.length);
		rewritten.write(original, 12, insertionOffset - 12);
		rewritten.write(insertion);
		rewritten.write(original, insertionOffset, original.length - insertionOffset);
		Files.write(vpk.toPath(), rewritten.toByteArray());
	}

	private static void testLooseContent() throws Exception {
		File mod = Files.createTempDirectory("csgo-content-loose").toFile();
		writeLooseContent(mod, Arrays.asList(REFERENCE_WEAPONS), null);
		GameContentValidator.Result result = GameContentValidator.validate(mod);
		assertStatus(GameContentValidator.Status.OK, result);
		if (result.getWeaponScriptCount() != REFERENCE_WEAPONS.length)
			throw new AssertionError("Expected the complete reference weapon script set");
		if (!REFERENCE_SET_SHA256.equals(GameContentValidator.getContractSha256()))
			throw new AssertionError("Reference basename-set digest drifted");
	}

	private static void testMissingManifestFailsClosed() throws Exception {
		File mod = Files.createTempDirectory("csgo-content-missing-manifest").toFile();
		assertStatus(GameContentValidator.Status.MISSING_WEAPON_MANIFEST,
			GameContentValidator.validate(mod));
	}

	private static void testMissingListedScriptFailsClosed() throws Exception {
		File mod = Files.createTempDirectory("csgo-content-missing-script").toFile();
		writeLooseContent(mod, Arrays.asList(REFERENCE_WEAPONS), "weapon_ak47");
		GameContentValidator.Result result = GameContentValidator.validate(mod);
		assertStatus(GameContentValidator.Status.MISSING_LISTED_WEAPON_SCRIPT, result);
		if (!result.getDiagnostic().contains("scripts/weapon_ak47"))
			throw new AssertionError("Diagnostic must identify the missing script");
	}

	private static void testHealthshotMustBeDeclared() throws Exception {
		File mod = Files.createTempDirectory("csgo-content-no-healthshot").toFile();
		List<String> withoutHealthshot = new ArrayList<String>(Arrays.asList(REFERENCE_WEAPONS));
		withoutHealthshot.remove("weapon_healthshot");
		writeLooseContent(mod, withoutHealthshot, null);
		assertStatus(GameContentValidator.Status.MISSING_REQUIRED_WEAPON_SCRIPT,
			GameContentValidator.validate(mod));
	}

	private static void testArbitraryFortyOneEntryManifestIsRejected() throws Exception {
		File mod = Files.createTempDirectory("csgo-content-wrong-contract").toFile();
		List<String> wrongContract = new ArrayList<String>(Arrays.asList(REFERENCE_WEAPONS));
		wrongContract.remove("weapon_ak47");
		wrongContract.add("weapon_not_in_1_36_0_2");
		writeLooseContent(mod, wrongContract, null);
		assertStatus(GameContentValidator.Status.INCOMPATIBLE_WEAPON_MANIFEST,
			GameContentValidator.validate(mod));
	}

	private static void testVpkContentIncludingExternalChunk() throws Exception {
		File mod = Files.createTempDirectory("csgo-content-vpk").toFile();
		List<TestEntry> entries = new ArrayList<TestEntry>();
		entries.add(new TestEntry("scripts/weapon_manifest.txt",
			manifest(REFERENCE_WEAPONS), false));
		for (String name : REFERENCE_WEAPONS) {
			entries.add(new TestEntry("scripts/" + name + ".txt", weaponScript(name),
				"weapon_healthshot".equals(name)));
		}
		writeVpk(mod, 2, entries.toArray(new TestEntry[entries.size()]));
		assertStatus(GameContentValidator.Status.OK, GameContentValidator.validate(mod));

		if (!new File(mod, "pak01_000.vpk").delete())
			throw new AssertionError("Could not remove test archive chunk");
		assertStatus(GameContentValidator.Status.INVALID_LISTED_WEAPON_SCRIPT,
			GameContentValidator.validate(mod));
	}

	private static void testReservedVpkArchiveIndexFailsClosed() throws Exception {
		File mod = Files.createTempDirectory("csgo-content-vpk-reserved-index").toFile();
		writeLooseContent(mod, Arrays.asList(REFERENCE_WEAPONS), null);
		String manifestText = manifest(REFERENCE_WEAPONS);
		writeVpk(mod, 2,
			new TestEntry("scripts/weapon_manifest.txt", manifestText, false));
		patchFirstVpkArchiveIndex(new File(mod, "pak01_dir.vpk"), 0xFFFF);
		Files.write(new File(mod, "pak01_65535.vpk").toPath(),
			manifestText.getBytes(StandardCharsets.UTF_8));

		assertStatus(GameContentValidator.Status.INVALID_CONTENT_ARCHIVE,
			GameContentValidator.validate(mod));
	}

	private static void testVpkVersionOne() throws Exception {
		File mod = Files.createTempDirectory("csgo-content-vpk-v1").toFile();
		List<TestEntry> entries = new ArrayList<TestEntry>();
		entries.add(new TestEntry("scripts/weapon_manifest.txt",
			manifest(REFERENCE_WEAPONS), false));
		for (String name : REFERENCE_WEAPONS)
			entries.add(new TestEntry("scripts/" + name + ".txt", weaponScript(name), false));
		writeVpk(mod, 1, entries.toArray(new TestEntry[entries.size()]));
		assertStatus(GameContentValidator.Status.OK, GameContentValidator.validate(mod));
	}

	private static void testOnlyCanonicalPakSequenceIsMounted() throws Exception {
		File backupOnly = Files.createTempDirectory("csgo-content-backup-vpk").toFile();
		List<TestEntry> complete = completeVpkEntries(manifest(REFERENCE_WEAPONS));
		writeVpk(backupOnly, "backup", 2,
			complete.toArray(new TestEntry[complete.size()]));
		assertStatus(GameContentValidator.Status.MISSING_WEAPON_MANIFEST,
			GameContentValidator.validate(backupOnly));

		File gap = Files.createTempDirectory("csgo-content-vpk-gap").toFile();
		List<TestEntry> pak01 = completeVpkEntries(manifest(REFERENCE_WEAPONS));
		for (int index = 0; index < pak01.size(); ++index) {
			if (pak01.get(index).path.equals("scripts/weapon_healthshot.txt")) {
				pak01.remove(index);
				break;
			}
		}
		writeVpk(gap, "pak01", 2, pak01.toArray(new TestEntry[pak01.size()]));
		writeVpk(gap, "pak03", 2,
			new TestEntry("scripts/weapon_healthshot.txt", weaponScript("weapon_healthshot"), false));
		assertStatus(GameContentValidator.Status.MISSING_LISTED_WEAPON_SCRIPT,
			GameContentValidator.validate(gap));
	}

	private static void testUnreadableCanonicalVpkFailsClosed() throws Exception {
		File mod = Files.createTempDirectory("csgo-content-unreadable-pak").toFile();
		Files.write(new File(mod, "pak01_dir.vpk").toPath(),
			new byte[] { 0x34, 0x12, (byte)0xaa, 0x55 });
		List<TestEntry> complete = completeVpkEntries(manifest(REFERENCE_WEAPONS));
		writeVpk(mod, "pak02", 2, complete.toArray(new TestEntry[complete.size()]));

		GameContentValidator.Result result = GameContentValidator.validate(mod);
		if (result.isValid())
			throw new AssertionError("Unreadable pak01_dir.vpk must fail closed before pak02");
		if (!result.getDiagnostic().contains("pak01_dir.vpk"))
			throw new AssertionError("Unreadable VPK diagnostic lacks pak01_dir.vpk: " +
				result.getDiagnostic());
	}

	private static void testDuplicateContractVpkPathFailsClosed() throws Exception {
		File mod = Files.createTempDirectory("csgo-content-duplicate-contract-path").toFile();
		List<TestEntry> entries = completeVpkEntries(manifest(REFERENCE_WEAPONS));
		entries.add(new TestEntry("scripts/weapon_manifest.txt", "not KeyValues\n", false));
		writeVpk(mod, 2, entries.toArray(new TestEntry[entries.size()]));

		GameContentValidator.Result result = GameContentValidator.validate(mod);
		if (result.isValid())
			throw new AssertionError("Duplicate weapon_manifest.txt must fail closed");
		if (!result.getDiagnostic().contains("duplicate contract entry path"))
			throw new AssertionError("Duplicate VPK diagnostic is not specific: " +
				result.getDiagnostic());
	}

	private static void testVpkPrecedesLooseFiles() throws Exception {
		File mod = Files.createTempDirectory("csgo-content-vpk-precedence").toFile();
		writeLooseContent(mod, Arrays.asList(REFERENCE_WEAPONS), null);
		writeVpk(mod, 2,
			new TestEntry("scripts/weapon_manifest.txt", "not KeyValues\n", false));
		assertStatus(GameContentValidator.Status.INVALID_WEAPON_MANIFEST,
			GameContentValidator.validate(mod));
	}

	private static void testUppercaseContractVpkKeyIsRejected() throws Exception {
		File mod = Files.createTempDirectory("csgo-content-uppercase-vpk-key").toFile();
		List<TestEntry> entries = completeVpkEntries(manifest(REFERENCE_WEAPONS));
		entries.remove(0);
		entries.add(new TestEntry("Scripts/weapon_manifest.txt",
			manifest(REFERENCE_WEAPONS), false));
		writeVpk(mod, 2, entries.toArray(new TestEntry[entries.size()]));
		GameContentValidator.Result result = GameContentValidator.validate(mod);
		assertStatus(GameContentValidator.Status.INVALID_CONTENT_ARCHIVE, result);
		if (!result.getDiagnostic().contains("noncanonical"))
			throw new AssertionError("Uppercase VPK key rejection must be diagnostic");
	}

	private static void testOpaqueCtxAndInvalidPlaintextFailClosed() throws Exception {
		File ctxOnly = Files.createTempDirectory("csgo-content-opaque-ctx").toFile();
		writeLooseContent(ctxOnly, Arrays.asList(REFERENCE_WEAPONS), "weapon_healthshot");
		writeText(new File(ctxOnly, "scripts/weapon_healthshot.ctx"), "opaque-not-validated\n");
		GameContentValidator.Result ctxResult = GameContentValidator.validate(ctxOnly);
		assertStatus(GameContentValidator.Status.INVALID_LISTED_WEAPON_SCRIPT, ctxResult);
		if (!ctxResult.getDiagnostic().contains("plaintext"))
			throw new AssertionError("CTX rejection must require a plaintext weapon script");

		String[] invalidScripts = {
			"WeaponData {}\n",
			"WeaponData { \"key\" }\n",
			"WrongRoot { \"key\" \"value\" }\n",
			"WeaponData { \"key\" \"value\" } trailing\n"
		};
		for (String invalid : invalidScripts) {
			File mod = Files.createTempDirectory("csgo-content-invalid-txt").toFile();
			writeLooseContent(mod, Arrays.asList(REFERENCE_WEAPONS), null);
			writeText(new File(mod, "scripts/weapon_healthshot.txt"), invalid);
			GameContentValidator.Result result = GameContentValidator.validate(mod);
			assertStatus(GameContentValidator.Status.INVALID_LISTED_WEAPON_SCRIPT, result);
			if (!result.getDiagnostic().contains("weapon_healthshot.txt"))
				throw new AssertionError("Invalid TXT diagnostic must identify its path");
		}
	}

	private static void testExcessiveKeyValuesDepthFailsClosed() throws Exception {
		File mod = Files.createTempDirectory("csgo-content-kv-depth").toFile();
		writeLooseContent(mod, Arrays.asList(REFERENCE_WEAPONS), null);
		StringBuilder deeplyNested = new StringBuilder("WeaponData\n{\n");
		for (int depth = 0; depth < 256; ++depth)
			deeplyNested.append("\"nested").append(depth).append("\"\n{\n");
		deeplyNested.append("\"value\" \"non-empty\"\n");
		for (int depth = 0; depth < 257; ++depth)
			deeplyNested.append("}\n");
		writeText(new File(mod, "scripts/weapon_healthshot.txt"), deeplyNested.toString());

		GameContentValidator.Result result = GameContentValidator.validate(mod);
		assertStatus(GameContentValidator.Status.INVALID_LISTED_WEAPON_SCRIPT, result);
		if (!result.getDiagnostic().contains("depth"))
			throw new AssertionError("Excessive KeyValues depth is not diagnostic: " +
				result.getDiagnostic());
	}

	private static void testVpkV2FooterIsExactAndOverflowSafe() throws Exception {
		List<TestEntry> complete = completeVpkEntries(manifest(REFERENCE_WEAPONS));

		File trailing = Files.createTempDirectory("csgo-content-v2-trailing").toFile();
		writeVpk(trailing, 2, complete.toArray(new TestEntry[complete.size()]));
		try (FileOutputStream output = new FileOutputStream(
			new File(trailing, "pak01_dir.vpk"), true)) {
			output.write(1);
		}
		assertStatus(GameContentValidator.Status.INVALID_CONTENT_ARCHIVE,
			GameContentValidator.validate(trailing));

		File overflow = Files.createTempDirectory("csgo-content-v2-overflow").toFile();
		writeVpk(overflow, 2, complete.toArray(new TestEntry[complete.size()]));
		File overflowVpk = new File(overflow, "pak01_dir.vpk");
		patchU32(overflowVpk, 16, 0xffffffffL);
		patchU32(overflowVpk, 20, 0xffffffffL);
		patchU32(overflowVpk, 24, 0xffffffffL);
		assertStatus(GameContentValidator.Status.INVALID_CONTENT_ARCHIVE,
			GameContentValidator.validate(overflow));

		File malformed = Files.createTempDirectory("csgo-content-v2-section").toFile();
		writeVpk(malformed, 2, complete.toArray(new TestEntry[complete.size()]));
		File malformedVpk = new File(malformed, "pak01_dir.vpk");
		patchU32(malformedVpk, 16, 1);
		try (FileOutputStream output = new FileOutputStream(malformedVpk, true)) {
			output.write(0);
		}
		assertStatus(GameContentValidator.Status.INVALID_CONTENT_ARCHIVE,
			GameContentValidator.validate(malformed));
	}

	private static void testPreparedValidationTokenIsPathBoundAndEngaged() throws Exception {
		File first = Files.createTempDirectory("csgo-content-token-a").toFile();
		File second = Files.createTempDirectory("csgo-content-token-b").toFile();
		writeLooseContent(first, Arrays.asList(REFERENCE_WEAPONS), null);
		writeLooseContent(second, Arrays.asList(REFERENCE_WEAPONS), null);

		GameContentValidator.Result validated = GameContentValidator.validate(first);
		String token = GameContentValidator.rememberSuccessfulValidation(first, validated);
		if (token == null || token.length() < 32)
			throw new AssertionError("Prepared validation token must have high entropy");
		if (GameContentValidator.findPreparedValidation(first, token) != validated)
			throw new AssertionError("Prepared result was not served from the process cache");
		if (GameContentValidator.findPreparedValidation(second, token) != null)
			throw new AssertionError("Prepared token must be bound to the canonical mod path");
		if (GameContentValidator.findPreparedValidation(first, token + "00") != null)
			throw new AssertionError("A forged prepared token must be rejected");

		if (!new File(first, "scripts/weapon_manifest.txt").delete())
			throw new AssertionError("Could not mutate test content after preparation");
		if (GameContentValidator.findPreparedValidation(first, token) != null)
			throw new AssertionError("Prepared token must be invalidated by content metadata drift");
		assertStatus(GameContentValidator.Status.MISSING_WEAPON_MANIFEST,
			GameContentValidator.validate(first));
	}

	private static void testPreparedTokenTracksFourDigitExternalChunk() throws Exception {
		File mod = Files.createTempDirectory("csgo-content-token-chunk-1000").toFile();
		List<TestEntry> entries = completeVpkEntries(manifest(REFERENCE_WEAPONS));
		writeVpk(mod, 2, entries.toArray(new TestEntry[entries.size()]));
		File chunk = new File(mod, "pak01_1000.vpk");
		Files.write(chunk.toPath(), new byte[] { 1, 2, 3 });

		GameContentValidator.Result validated = GameContentValidator.validate(mod);
		assertStatus(GameContentValidator.Status.OK, validated);
		String token = GameContentValidator.rememberSuccessfulValidation(mod, validated);
		if (GameContentValidator.findPreparedValidation(mod, token) != validated)
			throw new AssertionError("Four-digit chunk baseline was not cached");
		try (FileOutputStream output = new FileOutputStream(chunk, true)) {
			output.write(4);
		}
		if (GameContentValidator.findPreparedValidation(mod, token) != null)
			throw new AssertionError("pak01_1000.vpk metadata drift did not invalidate token");
	}

	private static void testDuplicateRawVpkGroupsFailClosed() throws Exception {
		List<TestEntry> complete = completeVpkEntries(manifest(REFERENCE_WEAPONS));

		File duplicateExtension = Files.createTempDirectory(
			"csgo-content-duplicate-extension").toFile();
		writeVpk(duplicateExtension, 2,
			complete.toArray(new TestEntry[complete.size()]));
		insertBeforeVpkTreeTail(new File(duplicateExtension, "pak01_dir.vpk"), 1,
			shadowExtensionGroup("txt", "shadow", "unrelated"));
		GameContentValidator.Result extensionResult =
			GameContentValidator.validate(duplicateExtension);
		assertStatus(GameContentValidator.Status.INVALID_CONTENT_ARCHIVE, extensionResult);
		if (!extensionResult.getDiagnostic().contains("duplicate extension group"))
			throw new AssertionError("Duplicate raw extension group was not diagnostic");

		File duplicateDirectory = Files.createTempDirectory(
			"csgo-content-duplicate-directory").toFile();
		writeVpk(duplicateDirectory, 2,
			complete.toArray(new TestEntry[complete.size()]));
		ByteArrayOutputStream shadows = new ByteArrayOutputStream();
		shadows.write(shadowDirectoryGroup("shadow", "first"));
		shadows.write(shadowDirectoryGroup("shadow", "second"));
		insertBeforeVpkTreeTail(new File(duplicateDirectory, "pak01_dir.vpk"), 2,
			shadows.toByteArray());
		GameContentValidator.Result directoryResult =
			GameContentValidator.validate(duplicateDirectory);
		assertStatus(GameContentValidator.Status.INVALID_CONTENT_ARCHIVE, directoryResult);
		if (!directoryResult.getDiagnostic().contains("duplicate directory group"))
			throw new AssertionError("Duplicate raw directory group was not diagnostic");
	}

	private static File createSiblingLayout(String prefix) throws Exception {
		File root = Files.createTempDirectory(prefix).toFile();
		File mod = new File(root, "csgo");
		if (!mod.mkdir())
			throw new AssertionError("Could not create test csgo directory");
		writeLooseContent(mod, Arrays.asList(REFERENCE_WEAPONS), null);
		return mod;
	}

	private static void assertOverlayRejected(File mod, String expectedName) {
		GameContentValidator.Result result = GameContentValidator.validate(mod);
		assertStatus(GameContentValidator.Status.UNSUPPORTED_AUTOMATIC_OVERLAY, result);
		if (!result.getDiagnostic().contains(expectedName))
			throw new AssertionError("Overlay diagnostic must identify " + expectedName);
	}

	private static void testNativeAutomaticSiblingOverlaysFailClosed() throws Exception {
		File xlsppatchMod = createSiblingLayout("csgo-content-xlsppatch");
		if (!new File(xlsppatchMod.getParentFile(), "xlsppatch").mkdir())
			throw new AssertionError("Could not create xlsppatch overlay");
		assertOverlayRejected(xlsppatchMod, "xlsppatch");

		File updateMod = createSiblingLayout("csgo-content-update");
		if (!new File(updateMod.getParentFile(), "update").mkdir())
			throw new AssertionError("Could not create update overlay");
		assertOverlayRejected(updateMod, "update");

		File dlcMod = createSiblingLayout("csgo-content-dlc");
		if (!new File(dlcMod.getParentFile(), "csgo_dlc1").mkdir())
			throw new AssertionError("Could not create active DLC overlay");
		assertOverlayRejected(dlcMod, "csgo_dlc1");
	}

	private static void testDisabledOrNoncontiguousDlcIsNotMounted() throws Exception {
		File disabledMod = createSiblingLayout("csgo-content-disabled-dlc");
		File disabledDlc = new File(disabledMod.getParentFile(), "csgo_dlc1");
		if (!disabledDlc.mkdir())
			throw new AssertionError("Could not create disabled DLC directory");
		writeText(new File(disabledDlc, "dlc_disabled.txt"), "disabled\n");
		assertStatus(GameContentValidator.Status.OK,
			GameContentValidator.validate(disabledMod));

		File gapMod = createSiblingLayout("csgo-content-dlc-gap");
		if (!new File(gapMod.getParentFile(), "csgo_dlc2").mkdir())
			throw new AssertionError("Could not create noncontiguous DLC directory");
		assertStatus(GameContentValidator.Status.OK,
			GameContentValidator.validate(gapMod));
	}

	private static void testOverlayCreationInvalidatesPreparedToken() throws Exception {
		File mod = createSiblingLayout("csgo-content-overlay-token");
		GameContentValidator.Result validated = GameContentValidator.validate(mod);
		assertStatus(GameContentValidator.Status.OK, validated);
		String token = GameContentValidator.rememberSuccessfulValidation(mod, validated);
		if (GameContentValidator.findPreparedValidation(mod, token) != validated)
			throw new AssertionError("Overlay-token baseline was not cached");
		if (!new File(mod.getParentFile(), "update").mkdir())
			throw new AssertionError("Could not create overlay after preparation");
		if (GameContentValidator.findPreparedValidation(mod, token) != null)
			throw new AssertionError("New native overlay did not invalidate prepared token");
		assertOverlayRejected(mod, "update");
	}

	private static void testPreparedValidationRejectsMutationBeforeCommit() throws Exception {
		File mod = Files.createTempDirectory("csgo-content-token-mutation").toFile();
		writeLooseContent(mod, Arrays.asList(REFERENCE_WEAPONS), null);
		GameContentValidator.Result validated = GameContentValidator.validate(mod);
		assertStatus(GameContentValidator.Status.OK, validated);

		writeText(new File(mod, "scripts/weapon_healthshot.txt"),
			"WeaponData { \"broken\" }\n");
		String token = GameContentValidator.rememberSuccessfulValidation(mod, validated);
		if (token != null)
			throw new AssertionError("Content changed after validation received a token");
		assertStatus(GameContentValidator.Status.INVALID_LISTED_WEAPON_SCRIPT,
			GameContentValidator.validate(mod));
	}

	public static void main(String[] args) throws Exception {
		testLooseContent();
		testMissingManifestFailsClosed();
		testMissingListedScriptFailsClosed();
		testHealthshotMustBeDeclared();
		testArbitraryFortyOneEntryManifestIsRejected();
		testVpkContentIncludingExternalChunk();
		testReservedVpkArchiveIndexFailsClosed();
		testVpkVersionOne();
		testOnlyCanonicalPakSequenceIsMounted();
		testUnreadableCanonicalVpkFailsClosed();
		testDuplicateContractVpkPathFailsClosed();
		testVpkPrecedesLooseFiles();
		testUppercaseContractVpkKeyIsRejected();
		testOpaqueCtxAndInvalidPlaintextFailClosed();
		testExcessiveKeyValuesDepthFailsClosed();
		testVpkV2FooterIsExactAndOverflowSafe();
		testPreparedValidationTokenIsPathBoundAndEngaged();
		testPreparedTokenTracksFourDigitExternalChunk();
		testDuplicateRawVpkGroupsFailClosed();
		testNativeAutomaticSiblingOverlaysFailClosed();
		testDisabledOrNoncontiguousDlcIsNotMounted();
		testOverlayCreationInvalidatesPreparedToken();
		testPreparedValidationRejectsMutationBeforeCommit();
		System.out.println("PASS: external CS:GO weapon content preflight");
	}
}
