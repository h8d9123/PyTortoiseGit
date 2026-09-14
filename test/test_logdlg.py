"""LogDlg（日志窗口）测试：加载、提交/文件右键菜单、过滤、动作入口。"""

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMenu, QMessageBox, QDialog


@pytest.fixture(autouse=True)
def _english_ui():
    from pytortoisegit.res import strings
    strings.set_language("en")
    yield
    strings.set_language("zh")


@pytest.fixture(autouse=True)
def _no_modals(monkeypatch):
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "warning",
                        staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))


def _logdlg(monkeypatch, repo, **kw):
    from pytortoisegit.dialogs import logdlg
    monkeypatch.setattr(logdlg, "run_async", lambda *a, **k: None)
    dlg = logdlg.LogDlg(repo, **kw)
    dlg._load_bg()
    dlg._on_loaded([])
    return dlg


class _FakeDlg:
    selected = "default"

    def __init__(self, *a, **k):
        pass

    def exec(self):
        return QDialog.DialogCode.Accepted

    def show(self):
        pass


def _patch_dialogs(monkeypatch, dlg):
    from pytortoisegit.dialogs import logdlg
    for path in ("pytortoisegit.dialogs.repobrowserdlg.RepositoryBrowserDlg",
                 "pytortoisegit.dialogs.mergedlg.MergeDlg",
                 "pytortoisegit.dialogs.resetdlg.ResetDlg",
                 "pytortoisegit.dialogs.gitswitchdlg.GitSwitchDlg",
                 "pytortoisegit.dialogs.exportdlg.ExportDlg",
                 "pytortoisegit.dialogs.formatpatchdlg.FormatPatchDlg",
                 "pytortoisegit.dialogs.commitisonrefsdlg.CommitIsOnRefsDlg",
                 "pytortoisegit.dialogs.createbranchdlg.CreateBranchDlg",
                 "pytortoisegit.dialogs.createbranchdlg.CreateTagDlg",
                 "pytortoisegit.dialogs.blamedlg.BlameDlg",
                 "pytortoisegit.dialogs.statgraphdlg.StatGraphDlg",
                 "pytortoisegit.dialogs.logorderingdlg.LogOrderingDlg"):
        monkeypatch.setattr(path, _FakeDlg)
    monkeypatch.setattr(logdlg, "DiffDlg", _FakeDlg)
    monkeypatch.setattr(logdlg, "LogDlg", _FakeDlg)
    monkeypatch.setattr("pytortoisegit.merge.mergefrm.MergeFrm", _FakeDlg)
    monkeypatch.setattr(dlg, "_do_simple", lambda args: None)


def test_logdlg_file_list(qapp, git_repo, monkeypatch):
    dlg = _logdlg(monkeypatch, git_repo)
    _patch_dialogs(monkeypatch, dlg)
    commit = list(dlg.log)[0]
    dlg._on_commit_selected(dlg.tree.topLevelItem(0), 0)
    groups = dlg._load_files_bg(commit.hash)
    dlg._on_files_loaded(groups)
    assert dlg.file_list.topLevelItemCount() >= 1
    dlg._on_file_double_clicked(dlg.file_list.topLevelItem(0), 0)


def test_logdlg_load_and_select(qapp, git_repo, monkeypatch):
    dlg = _logdlg(monkeypatch, git_repo)
    assert dlg.tree.topLevelItemCount() >= 1
    commits = list(dlg.log)
    assert commits
    item = dlg.tree.topLevelItem(0)
    dlg.tree.setCurrentItem(item)
    assert dlg._commit_of(item) is not None
    assert dlg._current_commit() is not None
    assert dlg._selected_commits()
    assert dlg._action_tip("M") is not None


def test_logdlg_fill_menu_single(qapp, git_repo, monkeypatch, auto_progress):
    dlg = _logdlg(monkeypatch, git_repo)
    _patch_dialogs(monkeypatch, dlg)
    commits = list(dlg.log)
    menu = QMenu(dlg)
    dlg._fill_log_menu(menu, [commits[0]])
    texts = [a.text() for a in menu.actions() if a.text()]
    assert any("Compare with working copy" in t for t in texts)
    for act in menu.actions():
        if act.isSeparator():
            continue
        if act.menu() is not None:
            for sub in act.menu().actions():
                sub.trigger()
        else:
            act.trigger()


def test_logdlg_fill_menu_two_and_multi(qapp, git_repo, monkeypatch, auto_progress):
    dlg = _logdlg(monkeypatch, git_repo)
    _patch_dialogs(monkeypatch, dlg)
    commits = list(dlg.log)
    menu = QMenu(dlg)
    dlg._fill_log_menu(menu, commits[:2])
    for act in menu.actions():
        if not act.isSeparator() and act.menu() is None:
            act.trigger()
    menu2 = QMenu(dlg)
    dlg._fill_log_menu(menu2, commits)
    for act in menu2.actions():
        if not act.isSeparator() and act.menu() is None:
            act.trigger()
    # 空列表直接返回
    dlg._fill_log_menu(QMenu(dlg), [])


def test_logdlg_file_menu(qapp, git_repo, monkeypatch, auto_progress, tmp_path):
    from PySide6.QtWidgets import QFileDialog
    dlg = _logdlg(monkeypatch, git_repo)
    _patch_dialogs(monkeypatch, dlg)
    commit = list(dlg.log)[0]
    copied = {}

    class _Clip:
        def copy_text(self, t):
            copied["t"] = t

    monkeypatch.setattr("pytortoisegit.utils.clipboard.ClipboardHelper", _Clip)
    dest = tmp_path / "out.txt"
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: (str(dest), "")))
    _menu, acts = dlg._build_file_menu()
    assert set(acts.values()) == {
        "base", "gnu", "wc", "log", "blame", "revert", "save", "view",
        "open", "openwith", "explore", "copy_full", "copy_rel", "copy_name"}
    for key in ("base", "gnu", "wc", "log", "blame", "revert", "save", "view",
                "open", "openwith", "explore", "copy_full", "copy_rel", "copy_name"):
        dlg._handle_file_menu(key, "a.txt", commit)
    assert copied["t"] == "a.txt"


def test_logdlg_filters_and_keys(qapp, git_repo, monkeypatch, auto_progress):
    from PySide6.QtGui import QKeyEvent
    dlg = _logdlg(monkeypatch, git_repo)
    _patch_dialogs(monkeypatch, dlg)
    dlg.filter_edit.setText("a.txt")
    dlg._apply_file_filter()
    dlg._apply_filter()
    dlg._sync_date_range()
    ev = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return,
                   Qt.KeyboardModifier.NoModifier)
    dlg.keyPressEvent(ev)
    dlg.button_open_diff()
    dlg._on_double_clicked(dlg.tree.topLevelItem(0), 0)
    dlg._on_stats()
    dlg._on_help()
    dlg._on_walk()          # 会 _populate()（清空树，放在最后）



