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
    # 未设置时用原版默认第一层命令（Sync/CreateRepo/Clone/Commit）
    assert MainMenuDlg._menu_top_commands(None) == {
        "sync", "repocreate", "clone", "commit"}


def test_menu_hidden_stale_all_falls_back_to_default(qapp, isolated_settings):
    """旧版本把“全部命令”写入隐藏列表时应自愈为默认值。"""
    from pytortoisegit.dialogs.mainmenu import MainMenuDlg
    from pytortoisegit.dialogs.settingsdlg import general_settings
    allc = MainMenuDlg._all_menu_commands()
    assert allc
    general_settings().setValue("contextMenuHideEntries", sorted(allc))
    assert MainMenuDlg._menu_hidden_commands(None) == {
        "svnignore", "stashapply", "subsync"}
    general_settings().setValue("contextMenuHideEntries", ["log", "blame"])
    assert MainMenuDlg._menu_hidden_commands(None) == {"log", "blame"}


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


def test_dialogs1_font_defaults_selectable_and_fallback(qapp,
                                                        isolated_settings):
    """字号下拉须含默认 9；已保存但不在下拉项里的字体/字号也要能显示。"""
    from pytortoisegit.dialogs.settingsdlg import _DialogsPage, general_settings
    page = _DialogsPage()
    page.load_settings()
    assert page._ctl["IDC_FONTSIZES"].currentText() == "9"
    general_settings().setValue("LogFontName", "MyCustomFont")
    general_settings().setValue("LogFontSize", "13")
    page2 = _DialogsPage()
    page2.load_settings()
    assert page2._ctl["IDC_FONTNAMES"].currentText() == "MyCustomFont"
    assert page2._ctl["IDC_FONTSIZES"].currentText() == "13"


def test_dialogs3_inherit_and_saveto_persist(qapp, isolated_settings):
    """Dialogs3 的 inherit 复选框与 Save to 下拉需持久化。"""
    from pytortoisegit.dialogs.settingsdlg import _Dialogs3Page
    page = _Dialogs3Page()
    page.load_settings()
    page._ctl["IDC_CHECK_INHERIT_LIMIT"].setChecked(True)
    page._ctl["IDC_CHECK_INHERIT_BORDER"].setChecked(True)
    page._ctl["IDC_CHECK_INHERIT_ICONPATH"].setChecked(True)
    page._ctl["IDC_COMBO_SETTINGS_SAFETO"].setCurrentIndex(1)  # Local
    page.save_settings()
    page2 = _Dialogs3Page()
    page2.load_settings()
    assert page2._ctl["IDC_CHECK_INHERIT_LIMIT"].isChecked()
    assert page2._ctl["IDC_CHECK_INHERIT_BORDER"].isChecked()
    assert page2._ctl["IDC_CHECK_INHERIT_ICONPATH"].isChecked()
    assert page2._ctl["IDC_COMBO_SETTINGS_SAFETO"].currentIndex() == 1


def test_overlay_handlers_regedit_cross_platform(qapp, isolated_settings,
                                                 monkeypatch):
    """非 Windows 平台点注册表按钮应提示，而不是跑 regedit.exe。"""
    from PySide6.QtWidgets import QMessageBox
    import pytortoisegit.dialogs.settingsdlg as sd
    called = []
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: called.append(1)))
    monkeypatch.setattr("sys.platform", "linux")
    page = sd._OverlayHandlersPage()
    page._open_regedit()
    assert called


def test_overlay_icons_list_has_previews(qapp, isolated_settings):
    """Icon Set 列表 9 项且带图标预览。"""
    from pytortoisegit.dialogs.settingsdlg import _OverlayIconsPage
    page = _OverlayIconsPage()
    tree = page._ctl["IDC_ICONLIST"]
    assert tree.topLevelItemCount() == 9
    assert not tree.topLevelItem(0).icon(0).isNull()


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
# 外部比较/合并工具设置
# ---------------------------------------------------------------------------

def test_diff_page_browse_enable_persist(qapp, isolated_settings, monkeypatch):
    from pytortoisegit.dialogs.settingsdlg import _DiffPage, general_settings
    monkeypatch.setattr("pytortoisegit.utils.pick.pick_open_file",
                        lambda *a, **k: "D:/BC/BCompare.exe")
    page = _DiffPage()
    page.load_settings()
    assert not page._ctl["IDC_EXTDIFF"].isEnabled()      # 默认内置
    page._ctl["IDC_EXTDIFF_ON"].click()                  # 选择“外部”
    assert page._ctl["IDC_EXTDIFF"].isEnabled()
    assert page._ctl["IDC_EXTDIFFBROWSE"].isEnabled()
    page._ctl["IDC_EXTDIFFBROWSE"].click()               # 浏览选择程序
    assert page._ctl["IDC_EXTDIFF"].text() == "D:/BC/BCompare.exe"
    page.save_settings()
    assert general_settings().value("DiffUseExternal", type=int) == 1
    page2 = _DiffPage()
    page2.load_settings()
    assert page2._ctl["IDC_EXTDIFF_ON"].isChecked()
    assert page2._ctl["IDC_EXTDIFF"].isEnabled()


def test_merge_page_enable_and_persist(qapp, isolated_settings, monkeypatch):
    from pytortoisegit.dialogs.settingsdlg import _MergePage, general_settings
    monkeypatch.setattr("pytortoisegit.utils.pick.pick_open_file",
                        lambda *a, **k: "D:/BC/BComp.exe")
    page = _MergePage()
    page.load_settings()
    assert not page._ctl["IDC_EXTMERGE"].isEnabled()
    page._ctl["IDC_EXTMERGE_ON"].click()
    page._ctl["IDC_EXTMERGEBROWSE"].click()
    page._ctl["IDC_MERGEBLOCK"].setChecked(True)
    assert page._ctl["IDC_EXTMERGE"].text() == "D:/BC/BComp.exe"
    page.save_settings()
    s = general_settings()
    assert s.value("MergeUseExternal", type=int) == 1
    assert s.value("MergeBlock", type=bool) is True


def test_diffdlg_use_external_setting(qapp, isolated_settings):
    from pytortoisegit.dialogs.diffdlg import DiffDlg
    from pytortoisegit.dialogs.settingsdlg import general_settings
    assert DiffDlg._use_external_diff() is False
    general_settings().setValue("DiffUseExternal", 1)
    assert DiffDlg._use_external_diff() is True


# ---------------------------------------------------------------------------
# 备用编辑器
# ---------------------------------------------------------------------------

def test_alternative_editor_browse_uses_open_dialog(qapp, isolated_settings,
                                                    monkeypatch):
    """选择编辑器应使用“打开”对话框，而非“保存”。"""
    from pytortoisegit.dialogs.settingsdlg import _AlternativeEditorPage
    called = {}
    monkeypatch.setattr("pytortoisegit.utils.pick.pick_open_file",
                        lambda *a, **k: called.setdefault("open", True) and "C:/ed.exe")
    monkeypatch.setattr("pytortoisegit.utils.pick.pick_file",
                        lambda *a, **k: called.setdefault("save", True) and "C:/bad.exe")
    page = _AlternativeEditorPage()
    page._ctl["IDC_ALTERNATIVEEDITOR_ON"].setChecked(True)
    page._ctl["IDC_ALTERNATIVEEDITORBROWSE"].click()
    assert called.get("open") is True
    assert "save" not in called
    assert page._ctl["IDC_ALTERNATIVEEDITOR"].text() == "C:/ed.exe"


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


# ---------------------------------------------------------------------------
# 颜色设置 → 消费端接线（改了颜色要真的影响渲染）
# ---------------------------------------------------------------------------

def test_status_color_reads_settings(qapp, isolated_settings):
    """日志文件列表状态色跟随 Colors1 设置。"""
    from pytortoisegit.dialogs import loglists
    from pytortoisegit.dialogs.settingsdlg import _Colors1Page, general_settings
    # 默认值：Modified = #0032a0
    assert loglists.status_color("M") == (0, 50, 160)
    general_settings().setValue("Colors/Modified", "#010203")
    loglists.invalidate()
    assert loglists.status_color("M") == (1, 2, 3)
    # Copied 沿用 Added
    assert loglists.status_color("C") == loglists.status_color("A")
    # 未知状态无颜色
    assert loglists.status_color("?") is None
    # 通过设置页保存也应生效（save_settings 内部失效缓存）
    page = _Colors1Page()
    page.load_settings()
    from pytortoisegit.dialogs import settingsdlg as sd
    sd._set_swatch(page._ctl["IDC_ADDEDCOLOR"], "#0a0b0c")
    page.save_settings()
    assert loglists.status_color("A") == (10, 11, 12)


def test_filediff_action_color_reads_settings(qapp, isolated_settings):
    from pytortoisegit.dialogs import loglists
    from pytortoisegit.dialogs.settingsdlg import general_settings
    general_settings().setValue("Colors/Added", "#111111")
    general_settings().setValue("Colors/Deleted", "#222222")
    loglists.invalidate()
    assert loglists.filediff_action_color("A") == (17, 17, 17)
    assert loglists.filediff_action_color("D") == (34, 34, 34)
    # 其余状态（M）用 Modified
    assert loglists.filediff_action_color("M") == (0, 50, 160)


def test_lane_color_line_width_node_size(qapp, isolated_settings):
    """日志图线色/线宽/节点大小跟随 Colors3 设置。"""
    from pytortoisegit.dialogs import loggraph
    from pytortoisegit.dialogs.settingsdlg import _Colors3Page, general_settings
    assert loggraph.line_width() == 2
    assert loggraph.node_size() == 10
    assert (loggraph.lane_color(0).red(), loggraph.lane_color(0).green(),
            loggraph.lane_color(0).blue()) == (0, 0, 0)

    page = _Colors3Page()
    page.load_settings()
    from pytortoisegit.dialogs import settingsdlg as sd
    sd._set_swatch(page._ctl["IDC_COLOR_LINE2"], "#123456")
    page._ctl["IDC_LOGGRAPHLINEWIDTH"].setCurrentText("5")
    page._ctl["IDC_LOGGRAPHNODESIZE"].setCurrentText("20")
    page.save_settings()

    c = loggraph.lane_color(1)
    assert (c.red(), c.green(), c.blue()) == (0x12, 0x34, 0x56)
    assert loggraph.line_width() == 5
    assert loggraph.node_size() == 20
    # 8 条线循环
    assert loggraph.lane_color(9).name() == loggraph.lane_color(1).name()


def test_restore_defaults_resets_whole_colors_page(qapp, isolated_settings):
    """Restore Default 需重置整页（颜色 + 复选框 + 下拉），不只颜色。"""
    from pytortoisegit.dialogs.settingsdlg import _Colors1Page, _Colors3Page
    from pytortoisegit.dialogs import settingsdlg as sd

    p1 = _Colors1Page()
    p1.load_settings()
    sd._set_swatch(p1._ctl["IDC_CONFLICTCOLOR"], "#123456")
    p1._ctl["IDC_DARKTHEME"].setChecked(True)
    p1._ctl["IDC_REVGRAPHUSELOCALFORCUR"].setChecked(True)
    p1._ctl["IDC_RESTORE"].click()
    assert p1._ctl["IDC_CONFLICTCOLOR"].text() == "#ff0000"
    assert not p1._ctl["IDC_DARKTHEME"].isChecked()
    assert not p1._ctl["IDC_REVGRAPHUSELOCALFORCUR"].isChecked()

    p3 = _Colors3Page()
    p3.load_settings()
    p3._ctl["IDC_COLOR_LINE1"].setText("#abcdef")
    p3._ctl["IDC_LOGGRAPHLINEWIDTH"].setCurrentText("7")
    p3._ctl["IDC_LOGGRAPHNODESIZE"].setCurrentText("25")
    p3._ctl["IDC_RESTORE"].click()
    assert p3._ctl["IDC_COLOR_LINE1"].text() == "#000000"
    assert p3._ctl["IDC_LOGGRAPHLINEWIDTH"].currentText() == "2"
    assert p3._ctl["IDC_LOGGRAPHNODESIZE"].currentText() == "10"


def test_swatch_text_contrast(qapp, isolated_settings):
    """色块文字按背景亮度自动黑/白，深色默认色也能看清。"""
    from pytortoisegit.dialogs.settingsdlg import _Colors1Page
    from pytortoisegit.dialogs import settingsdlg as sd
    assert sd._swatch_text_color("#000000") == "#ffffff"
    assert sd._swatch_text_color("#640000") == "#ffffff"
    assert sd._swatch_text_color("#ffffff") == "#000000"
    assert sd._swatch_text_color("#ffff00") == "#000000"
    p = _Colors1Page()
    p.load_settings()
    assert "#ffffff" in p._ctl["IDC_CONFLICTCOLOR"].styleSheet()


# ---------------------------------------------------------------------------
# Dialogs 1 设置 → 日志对话框消费端（条数/字体/相对时间）
# ---------------------------------------------------------------------------

def test_logdlg_reads_log_limit_font_relative_times(qapp, isolated_settings,
                                                    tmp_path):
    from pytortoisegit.dialogs import settingsdlg as sd
    from pytortoisegit.dialogs.logdlg import LogDlg
    s = sd.general_settings()
    s.setValue("NumberOfLogsScale", 3)     # Last N commits
    s.setValue("NumberOfLogs", "7")
    s.setValue("LogFontName", "Courier New")
    s.setValue("LogFontSize", "13")
    s.setValue("RelativeTimes", True)

    class R:
        def run(self, *a, **k):
            from types import SimpleNamespace
            return SimpleNamespace(stdout="", stderr="", returncode=0)

    class FakeRepo:
        name = "repo"
        runner = R()
        def current_branch(self): return "main"
    # 构造一个不真正加载的 LogDlg：monkeypatch run_async 阻止后台加载
    import pytortoisegit.dialogs.logdlg as logdlg_mod
    calls = []
    old_run_async = logdlg_mod.run_async
    logdlg_mod.run_async = lambda fn, *a, **k: calls.append(fn)
    try:
        dlg = LogDlg(FakeRepo())
    finally:
        logdlg_mod.run_async = old_run_async
    assert dlg._log_limit() == 7
    assert dlg._rel_times is True
    assert dlg.font().family() == "Courier New"
    assert dlg.font().pointSize() == 13


def test_log_limit_no_limit_loads_all(qapp, isolated_settings):
    from pytortoisegit.dialogs import settingsdlg as sd
    sd.general_settings().setValue("NumberOfLogsScale", 0)   # No limit
    from pytortoisegit.dialogs.logdlg import LogDlg
    assert LogDlg._log_limit.__get__ if False else True  # placeholder no-op
    # 直接验证：No limit 时 _log_limit 为 0（全部加载）
    class Dummy(LogDlg):
        def __init__(self): pass
    d = Dummy()
    assert d._log_limit() == 0


# ---------------------------------------------------------------------------
# Dialogs 2 设置 → 进度对话框消费端（显示计时 / 自动关闭）
# ---------------------------------------------------------------------------

def test_progress_run_git_shows_timing(qapp, isolated_settings, tmp_path,
                                       monkeypatch):
    from pytortoisegit.dialogs import settingsdlg as sd
    from pytortoisegit.dialogs.progress import ProgressDialog
    sd.general_settings().setValue("ShowGitexeTimings", True)

    class Runner:
        def run_interactive(self, *args):
            from types import SimpleNamespace
            return SimpleNamespace(stdout="out", stderr="", returncode=0)

    dlg = ProgressDialog()
    out = []
    dlg.log_async = lambda t: out.append(t)
    dlg.run = lambda fn: fn()          # 同步执行后台任务
    dlg.run_git(Runner(), "status")
    assert any("ms)" in str(t) for t in out)


def test_progress_autoclose_modes(qapp, isolated_settings):
    from pytortoisegit.dialogs import settingsdlg as sd
    from pytortoisegit.dialogs.progress import ProgressDialog
    s = sd.general_settings()
    # Manual：成功不自动关
    s.setValue("AutoCloseGitProgress", 0)
    dlg = ProgressDialog()
    dlg.accept = lambda: setattr(dlg, "_accepted", True)
    dlg._maybe_autoclose(True)
    assert not getattr(dlg, "_accepted", False)
    # If no errors：成功自动关
    s.setValue("AutoCloseGitProgress", 2)
    dlg2 = ProgressDialog()
    dlg2._accepted = False
    dlg2.accept = lambda: setattr(dlg2, "_accepted", True)
    dlg2._maybe_autoclose(True)
    from PySide6.QtTest import QTest
    QTest.qWait(600)
    assert dlg2._accepted is True
    # If no options：有 post action 时不关
    s.setValue("AutoCloseGitProgress", 1)
    dlg3 = ProgressDialog()
    dlg3.add_post_action("Again", lambda: None)
    dlg3._accepted = False
    dlg3.accept = lambda: setattr(dlg3, "_accepted", True)
    dlg3._maybe_autoclose(True)
    QTest.qWait(600)
    assert dlg3._accepted is False


# ---------------------------------------------------------------------------
# 未接线/平台不支持控件置灰
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cls_name,enabled_ids,disabled_ids", [
    ("_DialogsPage",
     ["IDC_DEFAULT_NUMBER_OF", "IDC_DEFAULT_SCALE",
      "IDC_FONTNAMES", "IDC_FONTSIZES", "IDC_RELATIVETIMES"],
     ["IDC_ENABLEGRAVATAR", "IDC_ENABLELOGCACHE", "IDC_SHOWDESCRIBE"]),
    ("_Dialogs2Page",
     ["IDC_AUTOCLOSECOMBO", "IDC_PROGRESSDLG_SHOW_TIMES"],
     ["IDC_AUTOCOMPLETION", "IDC_MAXHISTORY", "IDC_STRIPCOMMENTEDLINES"]),
    ("_Dialogs3Page",
     ["IDC_ICONFILE", "IDC_ICONFILE_BROWSE"],
     ["IDC_LANGCOMBO", "IDC_WARN_NO_SIGNED_OFF_BY",
      "IDC_RADIO_SETTINGS_GLOBAL", "IDC_COMBO_SETTINGS_SAFETO"]),
    ("_OverlayHandlersPage",
     ["IDC_REGEDT"],
     ["IDC_SHOWIGNOREDOVERLAY", "IDC_SHOWDELETEDOVERLAY"]),
    ("_OverlayIconsPage",
     ["IDC_ICONLIST"],
     ["IDC_ICONSETCOMBO", "IDC_LISTRADIO", "IDC_SYMBOLRADIO"]),
])
def test_unimplemented_controls_disabled(qapp, isolated_settings, monkeypatch,
                                         cls_name, enabled_ids, disabled_ids):
    """未接线的设置控件置灰；已接线的保留可用。"""
    import pytortoisegit.dialogs.settingsdlg as sd
    monkeypatch.setattr("sys.platform", "linux")
    page = getattr(sd, cls_name)()
    for cid in disabled_ids:
        assert page._ctl[cid].isEnabled() is False, cid
    for cid in enabled_ids:
        assert page._ctl[cid].isEnabled() is True, cid


def test_overlays_page_disabled_on_linux(qapp, isolated_settings, monkeypatch):
    """Overlays 页（Windows shell 专属）在非 Windows 整页置灰。"""
    import pytortoisegit.dialogs.settingsdlg as sd
    monkeypatch.setattr("sys.platform", "linux")
    page = sd._OverlayPage()
    assert page.isEnabled() is False
    assert page._ctl["IDC_ONLYEXPLORER"].isEnabled() is False
