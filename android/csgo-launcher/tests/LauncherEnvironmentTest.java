package com.valvesoftware;

import java.util.List;

public final class LauncherEnvironmentTest {
	private static void assertAssignment(LauncherEnvironment.Assignment actual,
		String name, String value) {
		if (!name.equals(actual.name) || !value.equals(actual.value))
			throw new AssertionError("Expected " + name + "=" + value + ", got " +
				actual.name + "=" + actual.value);
	}

	private static void expectFailure(String input) {
		try {
			LauncherEnvironment.parse(input);
			throw new AssertionError("Expected parser failure for: " + input);
		} catch (IllegalArgumentException expected) {
			// Expected.
		}
	}

	public static void main(String[] args) {
		List<LauncherEnvironment.Assignment> assignments = LauncherEnvironment.parse(
			"LIBGL_USEVBO=0; FOO=bar QUOTED=\"two words\" SINGLE='x y' EMPTY= ESCAPED=a\\ b");
		if (assignments.size() != 6)
			throw new AssertionError("Expected 6 assignments, got " + assignments.size());

		assertAssignment(assignments.get(0), "LIBGL_USEVBO", "0");
		assertAssignment(assignments.get(1), "FOO", "bar");
		assertAssignment(assignments.get(2), "QUOTED", "two words");
		assertAssignment(assignments.get(3), "SINGLE", "x y");
		assertAssignment(assignments.get(4), "EMPTY", "");
		assertAssignment(assignments.get(5), "ESCAPED", "a b");

		if (!LauncherEnvironment.parse("  ").isEmpty())
			throw new AssertionError("Blank input must produce no assignments");
		expectFailure("NO_EQUALS");
		expectFailure("9INVALID=value");
		expectFailure("BAD-NAME=value");
		expectFailure("OPEN=\"quote");
	}
}
