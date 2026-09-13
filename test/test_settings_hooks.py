"""设置页数据模型与 Hooks / BugTraq 列表页测试。"""

import pytest


@pytest.fixture()
def isolated_settings(tmp_path, monkeypatch):
    """把 general_settings 隔离到临时 INI 文件。"""
    from PySide6.QtCore import QSettings
    s = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(
        "pytortoisegit.dialogs.settingsdlg.general_settings", lambda: s)
    return s


def test_hook_model_roundtrip(isolated_settings):
    from pytortoisegit.dialogs.settings_data import Hook, load_hooks, save_hooks
    hooks = [
        Hook(htype="pre_commit_hook", path="C:/repo", commandline="run.bat",
             wait=True, show=False, enabled=True),
        Hook(htype="post_commit_hook", commandline="notify", local=True),
    ]
    save_hooks(hooks)
    loaded = load_hooks()
    assert len(loaded) == 2
    assert loaded[0].htype == "pre_commit_hook"
    assert loaded[0].commandline == "run.bat"
    assert loaded[0].show is False
    assert loaded[1].local is True


def test_bugtraq_model_roundtrip(isolated_settings):
    from pytortoisegit.dialogs.settings_data import (
        BugTraqAssociation, load_bugtraq_associations,
        save_bugtraq_associations)
    save_bugtraq_associations([
        BugTraqAssociation(path="C:/repo", provider="MyProvider",
                           parameters="p=1", enabled=False),
    ])
    loaded = load_bugtraq_associations()
    assert len(loaded) == 1
    assert loaded[0].provider == "MyProvider"
    assert loaded[0].enabled is False


def test_hooks_page_add_and_reload(qapp, isolated_settings):
    from pytortoisegit.dialogs.settingsdlg import _HooksPage
    from pytortoisegit.dialogs.settings_data import Hook
    page = _HooksPage()
    page.load_settings()
    assert page._ctl["IDC_HOOKLIST"].topLevelItemCount() == 0
    page._hooks.append(Hook(htype="pre_push_hook", commandline="echo hi"))
    page._reload()
    assert page._ctl["IDC_HOOKLIST"].topLevelItemCount() == 1
    page.save_settings()
    page2 = _HooksPage()
    page2.load_settings()
    assert page2._ctl["IDC_HOOKLIST"].topLevelItemCount() == 1


def test_bugtraq_page_reload(qapp, isolated_settings):
    from pytortoisegit.dialogs.settingsdlg import _BugTraqPage
    from pytortoisegit.dialogs.settings_data import BugTraqAssociation
    page = _BugTraqPage()
    page.load_settings()
    page._assocs.append(BugTraqAssociation(path="C:/repo", provider="P"))
    page._reload()
    assert page._ctl["IDC_BUGTRAQLIST"].topLevelItemCount() == 1
    page.save_settings()
    page2 = _BugTraqPage()
    page2.load_settings()
    assert page2._ctl["IDC_BUGTRAQLIST"].topLevelItemCount() == 1


def test_hook_config_dialog_fields(qapp):
    from pytortoisegit.dialogs.settingsdlg import HookConfigDlg
    from pytortoisegit.dialogs.settings_data import Hook
    dlg = HookConfigDlg(hook=Hook(htype="post_push_hook", path="C:/r",
                                  commandline="cmd.exe", wait=False,
                                  show=False, enabled=False))
    assert dlg._ctl["IDC_HOOKTYPECOMBO"].count() == 6
    assert dlg._ctl["IDC_HOOKTYPECOMBO"].currentData() == "post_push_hook"
    assert dlg._ctl["IDC_HOOKCOMMANDLINE"].text() == "cmd.exe"
    assert dlg._ctl["IDC_WAITCHECK"].isChecked() is False
    assert dlg._ctl["IDC_HIDECHECK"].isChecked() is True
    assert dlg._ctl["IDC_ENABLE"].isChecked() is False


def test_bugtraq_config_dialog_fields(qapp):
    from pytortoisegit.dialogs.settingsdlg import BugTraqConfigDlg
    from pytortoisegit.dialogs.settings_data import BugTraqAssociation
    dlg = BugTraqConfigDlg(assoc=BugTraqAssociation(
        path="C:/r", provider="Prov", parameters="a=b", enabled=True))
    assert dlg._ctl["IDC_BUGTRAQPATH"].text() == "C:/r"
    assert dlg._ctl["IDC_BUGTRAQPROVIDERCOMBO"].currentText() == "Prov"
    assert dlg._ctl["IDC_BUGTRAQPARAMETERS"].text() == "a=b"
