"""Tests for HEAR-089: Fix Installer Install-Root Derivation Edge Cases.

The Inno Setup GetInstallRoot function must derive the correct install root for
both the default path (ending in \\app) and user-customised paths that do NOT
end in \\app.

Pascal logic mirrored here so it can be unit-tested without running Inno Setup:

  if LowerCase(ExtractFileName(wizard_dir)) == 'app':
      return parent_dir(wizard_dir)
  else:
      return wizard_dir
"""
from __future__ import annotations

import re
from pathlib import Path, PureWindowsPath

import pytest


# ---------------------------------------------------------------------------
# Python simulation of the Inno Setup GetInstallRoot Pascal function
# ---------------------------------------------------------------------------

def _get_install_root(wizard_dir_value: str) -> str:
    """Mirror of the corrected Pascal GetInstallRoot(Param) function.

    Uses PureWindowsPath so tests run cross-platform (no real filesystem needed).
    """
    p = PureWindowsPath(wizard_dir_value)
    if p.name.lower() == "app":
        parent = str(p.parent)
        return parent
    return wizard_dir_value


# ---------------------------------------------------------------------------
# AC1: GetInstallRoot handles both <root>\\app and custom <root> selections
# ---------------------------------------------------------------------------

class TestGetInstallRootAppSuffix:
    def test_default_path_returns_parent(self):
        """DefaultDirName = C:\\AyeHear\\app  →  C:\\AyeHear."""
        result = _get_install_root(r"C:\AyeHear\app")
        assert result == r"C:\AyeHear"

    def test_custom_drive_with_app_suffix(self):
        """D:\\MyInstall\\app  →  D:\\MyInstall (preserves selected drive)."""
        result = _get_install_root(r"D:\MyInstall\app")
        assert result == r"D:\MyInstall"

    def test_deep_path_with_app_suffix(self):
        """E:\\Company\\AYEHear\\app  →  E:\\Company\\AYEHear."""
        result = _get_install_root(r"E:\Company\AYEHear\app")
        assert result == r"E:\Company\AYEHear"

    def test_uppercase_APP_normalised(self):
        """\\APP suffix (uppercase) must also be treated as the app folder."""
        result = _get_install_root(r"C:\AyeHear\APP")
        assert result == r"C:\AyeHear"

    def test_mixed_case_App_normalised(self):
        result = _get_install_root(r"D:\AyeHear\App")
        assert result == r"D:\AyeHear"


class TestGetInstallRootCustomPathNoSuffix:
    def test_custom_path_without_app_returns_as_is(self):
        """D:\\AyeHear  →  D:\\AyeHear (no extra ascent)."""
        result = _get_install_root(r"D:\AyeHear")
        assert result == r"D:\AyeHear"

    def test_nested_custom_path_without_app_returns_as_is(self):
        """D:\\Programs\\AyeHear  →  D:\\Programs\\AyeHear (no ascent)."""
        result = _get_install_root(r"D:\Programs\AyeHear")
        assert result == r"D:\Programs\AyeHear"

    def test_root_drive_without_app_returns_as_is(self):
        """Installing directly to C:\\  →  C:\\ (edge case, root stays root)."""
        result = _get_install_root(r"C:\\")
        assert result == r"C:\\"

    def test_custom_folder_named_differently(self):
        """Any folder name that is not 'app' is the install root itself."""
        result = _get_install_root(r"C:\AyeHearSoftware")
        assert result == r"C:\AyeHearSoftware"


class TestGetInstallRootNonDefaultDriveRoundtrip:
    def test_default_logic_on_non_default_drive(self):
        """HEAR-086 scenario: D:\\AyeHear\\app must not shift to D:\\."""
        wizard_value = r"D:\AyeHear\app"
        root = _get_install_root(wizard_value)
        assert root == r"D:\AyeHear"
        # Critical: must NOT be a drive root
        assert root != r"D:\\"
        assert root != "D:"

    def test_no_extra_ascent_for_plain_custom_dir(self):
        """HEAR-089 AC1: D:\\AyeHear (no app) must stay D:\\AyeHear not D:\\."""
        wizard_value = r"D:\AyeHear"
        root = _get_install_root(wizard_value)
        assert root == r"D:\AyeHear"
        # Would have been wrong with old ExtractFileDir-always approach
        assert root != r"D:\\"


# ---------------------------------------------------------------------------
# AC3: ISS file contains the corrected GetInstallRoot implementation
# ---------------------------------------------------------------------------

class TestInstallerScriptContent:
    _ISS_PATH = Path(__file__).parent.parent / "build" / "installer" / "ayehear-installer.iss"

    def test_iss_file_exists(self):
        assert self._ISS_PATH.exists(), "Installer ISS script not found"

    def test_get_install_root_not_simple_extract_file_dir(self):
        """Old implementation was a one-liner; corrected version has a branch."""
        content = self._ISS_PATH.read_text(encoding="utf-8", errors="replace")
        # Must NOT be the old one-liner that always calls ExtractFileDir
        old_oneliner = re.search(
            r"function GetInstallRoot.*?begin\s*Result\s*:=\s*ExtractFileDir\(WizardDirValue\);\s*end;",
            content,
            re.DOTALL | re.IGNORECASE,
        )
        assert old_oneliner is None, (
            "Old GetInstallRoot one-liner detected — HEAR-089 fix not applied"
        )

    def test_get_install_root_has_app_branch(self):
        """Corrected implementation checks for the 'app' folder name."""
        content = self._ISS_PATH.read_text(encoding="utf-8", errors="replace")
        assert "'app'" in content.lower(), (
            "Expected app-name check in GetInstallRoot"
        )

    def test_get_install_root_has_conditional(self):
        """Corrected function must contain an if/else branch."""
        content = self._ISS_PATH.read_text(encoding="utf-8", errors="replace")
        func_match = re.search(
            r"function GetInstallRoot.*?end;",
            content,
            re.DOTALL | re.IGNORECASE,
        )
        assert func_match is not None, "GetInstallRoot function not found in ISS"
        func_body = func_match.group(0)
        assert re.search(r"\bif\b", func_body, re.IGNORECASE), (
            "GetInstallRoot must contain a conditional branch (if)"
        )

    def test_install_dir_env_var_still_set_in_registry(self):
        """AYEHEAR_INSTALL_DIR registry entry must use GetInstallRoot."""
        content = self._ISS_PATH.read_text(encoding="utf-8", errors="replace")
        assert "AYEHEAR_INSTALL_DIR" in content
        assert "GetInstallRoot" in content
