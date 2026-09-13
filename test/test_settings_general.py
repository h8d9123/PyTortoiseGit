"""「常规」设置子页自动化测试：尽量用 QTest 模拟真实用户输入。

覆盖：General / 右键菜单 / 右键菜单2 / Win11 / 对话框1-3 / 颜色1-3 / 备用编辑器。
"""

import shutil

import pytest
from PySide6.QtCore import Qt


@pytest.fixture()
def isolated_settings(tmp_path, monkeypatch):
    """把 general_settings 隔离到临时 INI 文件，避免污染真实注册表。"""
    from PySide6.QtCore import QSettings
    s = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(
        "pytortoisegit.dialogs.settingsdlg.general_settings", lambda: s)
    return s


@pytest.fixture()
def restore_language():
    """测试结束后恢复界面语言，避免污染其它用例。"""
    from pytortoisegit.res import strings
    before = strings.get_language()
    yield
    strings.set_language(before)


# ---------------------------------------------------------------------------
# General
# ---------------------------------------------------------------------------

def test_general_language_switch(qapp, isolated_settings, ui, restore_language):
    from pytortoisegit.dialogs.settingsdlg import _GeneralPage, general_settings
    from pytortoisegit.res import strings
    page = _GeneralPage()
    page.setup()
    page.load_from_settings()
    ui.set_combo(page.language_combo, "English")
    page.apply_to_settings()
    assert general_settings().value("language") == "English"
    assert strings.get_language() == "en"


def test_general_git_check_shows_version(qapp, isolated_settings):
    page = _general_page()
    git = shutil.which("git")
    if not git:
        pytest.skip("git 未安装")
    page.git_path_edit.setText(git)
    page._check_git()
    assert "git version" in page.version_label.text().lower()


def test_general_browse_fills_path(qapp, isolated_settings, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    monkeypatch.setattr(QFileDialog, "getExistingDirectory",
                        lambda *a, **k: "C:/fake/git")
    page = _general_page()
    page._on_browse()
    assert page.git_path_edit.text() == "C:/fake/git"


def test_general_apply_persists(qapp, isolated_settings):
    from pytortoisegit.dialogs.settingsdlg import general_settings
    page = _general_page()
    page.check_newer_checkbox.click()            # 用户点击复选框
    page.git_path_edit.setText("C:/g/git.exe")
    page.extern_path_edit.setText("C:/g/usr/bin")
    page.apply_to_settings()
    s = general_settings()
    assert s.value("checkNewer", type=bool) is False
    assert s.value("gitPath") == "C:/g/git.exe"
    assert s.value("extraPath") == "C:/g/usr/bin"


def _bind_git_settings(monkeypatch, isolated_settings):
    """让 git.py 的 _settings_value 读取隔离设置。"""
    import pytortoisegit.git.git as gitmod
    monkeypatch.setattr(
        gitmod, "_settings_value",
        lambda k, d="": str(isolated_settings.value(k, d) or d))


def test_general_gitpath_used_by_runner(qapp, isolated_settings, tmp_path,
                                        monkeypatch):
    monkeypatch.delenv("GIT_PATH", raising=False)
    _bind_git_settings(monkeypatch, isolated_settings)
    fake = tmp_path / "git.exe"
    fake.write_text("", encoding="utf-8")
    isolated_settings.setValue("gitPath", str(fake))
    from pytortoisegit.git.git import find_git_executable
    assert find_git_executable() == str(fake)


def test_general_extrapath_injected(qapp, isolated_settings, monkeypatch):
    _bind_git_settings(monkeypatch, isolated_settings)
    isolated_settings.setValue("extraPath", "C:/extra/bin")
    from pytortoisegit.git.git import GitRunner
    runner = GitRunner(git_executable="git")
    assert runner.env["PATH"].startswith("C:/extra/bin")


def _general_page():
    from pytortoisegit.dialogs.settingsdlg import _GeneralPage
    page = _GeneralPage()
    page.setup()
    page.load_from_settings()
    return page


# ---------------------------------------------------------------------------
# 右键菜单 / 右键菜单2
# ---------------------------------------------------------------------------

def _checked_commands(tree):
    return {tree.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole)
            for i in range(tree.topLevelItemCount())
            if tree.topLevelItem(i).checkState(0) == Qt.CheckState.Checked}


def test_context_menu_default_and_toggle(qapp, isolated_settings, ui):
    from pytortoisegit.dialogs.settingsdlg import _ContextMenuPage, general_settings
    page = _ContextMenuPage()
    tree = page._ctl["IDC_MENULIST"]
    assert _checked_commands(tree) == {"sync", "repocreate", "clone", "commit"}
    # 用户勾选 push
    for i in range(tree.topLevelItemCount()):
        it = tree.topLevelItem(i)
        if it.data(0, Qt.ItemDataRole.UserRole) == "push":
            it.setCheckState(0, Qt.CheckState.Checked)
    page.save_to_settings()
    assert "push" in general_settings().value("contextMenuEntries")


def test_context_menu_select_all_and_restore(qapp, isolated_settings):
    from pytortoisegit.dialogs.settingsdlg import _ContextMenuPage
    page = _ContextMenuPage()
    tree = page._ctl["IDC_MENULIST"]
    page._ctl["IDC_SELECTALL"].click()            # 全选
    assert all(tree.topLevelItem(i).checkState(0) == Qt.CheckState.Checked
               for i in range(tree.topLevelItemCount()))
    page._ctl["IDC_RESTORE"].click()              # 恢复默认
    assert _checked_commands(tree) == {"sync", "repocreate", "clone", "commit"}


def test_context_menu_flags_persist(qapp, isolated_settings):
    from pytortoisegit.dialogs.settingsdlg import _ContextMenuPage, general_settings
    page = _ContextMenuPage()
    page.load_settings()
    page._ctl["IDC_HIDEMENUS"].click()
    page._ctl["IDC_ENABLEDRAGCONTEXTMENU"].click()
    page._set_widget_text(page._ctl["IDC_NOCONTEXTPATHS"], "C:/skip")
    page.save_settings()
    s = general_settings()
    assert s.value("HideMenusForUnversionedItems", type=bool) is True
    assert s.value("EnableDragContextMenu", type=bool) is False
    assert s.value("NoContextPaths") == "C:/skip"


def test_context_menu2_default_and_hidden(qapp, isolated_settings, ui):
    from pytortoisegit.dialogs.settingsdlg import _ContextMenu2Page
    page = _ContextMenu2Page()
    tree = page._ctl["IDC_MENULIST"]
    assert _checked_commands(tree) == {"svnignore", "stashapply", "subsync"}
    ui.click(page._ctl["IDC_RESTORE"])
    assert _checked_commands(tree) == {"svnignore", "stashapply", "subsync"}


def test_menu_hidden_and_top_commands(qapp, isolated_settings):
    from pytortoisegit.dialogs.mainmenu import MainMenuDlg
    assert MainMenuDlg._menu_hidden_commands(None) == {
        "svnignore", "stashapply", "subsync"}
    assert MainMenuDlg._menu_top_commands(None) is None


def test_no_context_path_and_hide_unversioned(qapp, isolated_settings, tmp_path):
    from pytortoisegit.dialogs.settingsdlg import general_settings
    from pytortoisegit.dialogs.mainmenu import MainMenuDlg
    general_settings().setValue("NoContextPaths", str(tmp_path))
    assert MainMenuDlg._is_no_context_path(str(tmp_path / "sub"))
    assert not MainMenuDlg._is_no_context_path(str(tmp_path.parent / "other"))
    general_settings().setValue("HideMenusForUnversionedItems", True)
    assert MainMenuDlg._hide_unversioned_menus() is True


# ---------------------------------------------------------------------------
# 对话框 1/2/3
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cls_name", [
    "_DialogsPage", "_Dialogs2Page", "_Colors1Page", "_Colors2Page",
    "_Colors3Page", "_BlamePage", "_UDiffPage"])
def test_settings_bool_roundtrip(qapp, isolated_settings, cls_name):
    from pytortoisegit.dialogs import settingsdlg as sd
    cls = getattr(sd, cls_name)
    page = cls()
    page.load_settings()
    bools = [(key, cid) for key, cid, kind, _ in getattr(page, "_SETTINGS", [])
             if kind == "bool" and page._ctl.get(cid) is not None]
    if not bools:
        pytest.skip("无布尔选项")
    for _key, cid in bools:
        page._ctl[cid].setChecked(not page._ctl[cid].isChecked())
    page.save_settings()
    page2 = cls()
    page2.load_settings()
    for key, cid in bools:
        assert page._ctl[cid].isChecked() == page2._ctl[cid].isChecked(), key


@pytest.mark.parametrize("cls_name", ["_DialogsPage", "_Dialogs2Page"])
def test_settings_text_roundtrip(qapp, isolated_settings, cls_name):
    from pytortoisegit.dialogs import settingsdlg as sd
    cls = getattr(sd, cls_name)
    page = cls()
    page.load_settings()
    expected = {}
    for key, cid, kind, default in getattr(page, "_SETTINGS", []):
        w = page._ctl.get(cid)
        if w is None or kind != "text":
            continue
        page._set_widget_text(w, "99")
        expected[cid] = page._get_widget_text(w)
    page.save_settings()
    page2 = cls()
    page2.load_settings()
    for key, cid, kind, default in getattr(page, "_SETTINGS", []):
        if cid not in expected:
            continue
        assert page2._get_widget_text(page2._ctl[cid]) == expected[cid], key


def test_dialogs3_config_source_radio(qapp, isolated_settings):
    from pytortoisegit.dialogs.settingsdlg import _Dialogs3Page, general_settings
    page = _Dialogs3Page()
    page.load_settings()
    page._ctl["IDC_RADIO_SETTINGS_GLOBAL"].setChecked(True)
    page.save_settings()
    assert general_settings().value("Dialogs3ConfigSource", type=int) == 3
    page2 = _Dialogs3Page()
    page2.load_settings()
    assert page2._ctl["IDC_RADIO_SETTINGS_GLOBAL"].isChecked()


def test_dialogs3_combos_populated(qapp, isolated_settings):
    from pytortoisegit.dialogs.settingsdlg import _Dialogs3Page
    page = _Dialogs3Page()
    assert page._ctl["IDC_LANGCOMBO"].count() >= 1
    assert page._ctl["IDC_WARN_NO_SIGNED_OFF_BY"].count() == 3


# ---------------------------------------------------------------------------
# 颜色 1/2/3
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cls_name,cid,default", [
    ("_Colors1Page", "IDC_CONFLICTCOLOR", "#ff0000"),
    ("_Colors2Page", "IDC_CURRENT_BRANCH", "#c80000"),
    ("_Colors3Page", "IDC_COLOR_LINE1", "#000000"),
])
def test_color_pick_persist_restore(qapp, isolated_settings, monkeypatch,
                                    cls_name, cid, default):
    from pytortoisegit.dialogs import settingsdlg as sd
    monkeypatch.setattr(sd, "_pick_color", lambda parent, cur: "#123456")
    cls = getattr(sd, cls_name)
    page = cls()
    page.load_settings()
    btn = page._ctl[cid]
    btn.click()                                   # 用户点击颜色块并选色
    assert btn.text() == "#123456"
    page.save_settings()
    page2 = cls()
    page2.load_settings()
    assert page2._ctl[cid].text() == "#123456"
    page2._ctl["IDC_RESTORE"].click()             # 恢复默认
    assert page2._ctl[cid].text() == default


def test_colors3_line_width_node_size(qapp, isolated_settings, ui):
    from pytortoisegit.dialogs.settingsdlg import _Colors3Page, general_settings
    page = _Colors3Page()
    page.load_settings()
    ui.set_combo(page._ctl["IDC_LOGGRAPHLINEWIDTH"], "3")
    ui.set_combo(page._ctl["IDC_LOGGRAPHNODESIZE"], "12")
    page.save_settings()
    s = general_settings()
    assert s.value("LogLineWidth") == "3"
    assert s.value("LogNodeSize") == "12"


# ---------------------------------------------------------------------------
# 备用编辑器
# ---------------------------------------------------------------------------

def test_alternative_editor_toggle_and_persist(qapp, isolated_settings):
    from pytortoisegit.dialogs.settingsdlg import (
        _AlternativeEditorPage, general_settings)
    page = _AlternativeEditorPage()
    page.load_settings()
    page._ctl["IDC_ALTERNATIVEEDITOR_ON"].click()       # 选择“自定义”
    assert page._ctl["IDC_ALTERNATIVEEDITOR"].isEnabled()
    page._ctl["IDC_ALTERNATIVEEDITOR"].setText("C:/editor.exe")
    page.save_settings()
    s = general_settings()
    assert s.value("AlternativeEditorUseCustom", type=int) == 1
    assert s.value("AlternativeEditor") == "C:/editor.exe"
    page2 = _AlternativeEditorPage()
    page2.load_settings()
    assert page2._ctl["IDC_ALTERNATIVEEDITOR_ON"].isChecked()
    page2._ctl["IDC_ALTERNATIVEEDITOR_OFF"].click()     # 切回记事本
    assert not page2._ctl["IDC_ALTERNATIVEEDITOR"].isEnabled()
