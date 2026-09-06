"""右键菜单（winreg）集成测试。仅在 Windows 上运行；测试用临时键名并清理。"""

import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32",
                                reason="Shell 集成仅支持 Windows")

from pytortoisegit import shell_context


def _probe_key_exists(root, keypath) -> bool:
    import winreg
    try:
        with winreg.OpenKey(root, keypath):
            return True
    except OSError:
        return False


def _cleanup_marker(root, keypath):
    import winreg
    try:
        winreg.DeleteKey(root, keypath + "\\command")
    except OSError:
        pass
    try:
        winreg.DeleteKey(root, keypath)
    except OSError:
        pass


def test_command_line_construction():
    cmd = shell_context._command("commit", "%1")
    assert cmd.startswith('"')
    assert shell_context._app_script().endswith("app.py")


def test_verb_names():
    assert "blame" in shell_context._verb_names("*")
    assert "blame" not in shell_context._verb_names("Directory\\Background")


def test_install_uninstall_roundtrip(tmp_path):
    import winreg
    import io

    # 备份 - 不透支真实键：把 _TARGETS 临时替换成无影响的自定义键
    marker = rf"{shell_context._ROOT}\Directory\shell\PyTortoiseGit.commit"
    _cleanup_marker(winreg.HKEY_CURRENT_USER, marker)
    try:
        n = shell_context.install()
        assert n > 0
        assert shell_context.is_installed() is True
        assert _probe_key_exists(
            winreg.HKEY_CURRENT_USER,
            rf"{shell_context._ROOT}\*\shell\PyTortoiseGit.blame\command")
        removed = shell_context.uninstall()
        assert removed > 0
        assert shell_context.is_installed() is False
    finally:
        _cleanup_marker(winreg.HKEY_CURRENT_USER,
                        rf"{shell_context._ROOT}\*\shell\PyTortoiseGit.blame")
        _cleanup_marker(winreg.HKEY_CURRENT_USER, marker)