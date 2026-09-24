"""右键菜单涉及的子对话框测试（使用真实对话框，而非 fake）。

覆盖：BlameDlg / BrowseRefsDlg / SelectRemoteRefDlg / MergeAbortDlg /
ResolveDlg / IgnoreDlg —— 这些正是菜单动作实际打开的真实子对话框。
"""

from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QDialog


@pytest.fixture(autouse=True)
def _english_ui():
    from pytortoisegit.res import strings
    strings.set_language("en")
    yield
    strings.set_language("zh")


# ---------------------------------------------------------------------------
# BlameDlg（菜单：复制哈希 / 短哈希 / 显示日志）
# ---------------------------------------------------------------------------

def test_blame_dlg_load_and_menu(qapp, git_repo, monkeypatch):
    from pytortoisegit.dialogs.blamedlg import BlameDlg
    copied = {}

    class _FakeClip:
        def copy_text(self, text):
            copied["t"] = text

    monkeypatch.setattr("pytortoisegit.utils.clipboard.ClipboardHelper",
                        _FakeClip)
    dlg = BlameDlg(git_repo, "a.txt")
    data = dlg._blame_bg()
    assert data.lines
    dlg._on_loaded(data)
    lines = data.lines
    assert dlg.table.rowCount() == len(lines)
    assert dlg.log_table.rowCount() == len(dlg._sha_order)
    assert dlg.log_table.rowCount() >= 1

    sha = lines[0].sha
    dlg._handle_menu("copy", sha)
    assert copied["t"] == sha
    dlg._handle_menu("copy_short", sha)
    assert copied["t"] == str(sha)[:8]
    dlg.table.selectRow(0)
    dlg._handle_menu("copy_log", sha)
    assert sha in copied["t"] and lines[0].author in copied["t"]

    opened = {}

    class _FakeLog:
        def __init__(self, *a, **k):
            opened["y"] = True

        def exec(self):
            return 0

        def show(self):
            pass

    monkeypatch.setattr("pytortoisegit.dialogs.logdlg.LogDlg", _FakeLog)
    dlg._handle_menu("log", sha)
    assert opened.get("y")

    _menu, acts = dlg._build_menu_context()
    assert set(acts.values()) == {
        "copy", "copy_short", "copy_log", "blame_prev", "compare_prev", "log"}
    assert dlg._sha_at(QPoint(0, 0)) in (None, sha)
    # 选中行后属性面板应显示提交信息
    dlg.table.selectRow(0)
    assert dlg._prop_items["sha"].text(1) == sha


def test_blame_dlg_positions_on_line(qapp, git_repo):
    from pytortoisegit.dialogs.blamedlg import BlameDlg
    dlg = BlameDlg(git_repo, "a.txt", line=2)
    dlg._on_loaded(dlg._blame_bg())
    assert dlg.table.currentRow() == 1


def test_blame_dlg_find(qapp, git_repo):
    from pytortoisegit.dialogs.blamedlg import BlameDlg
    dlg = BlameDlg(git_repo, "a.txt")
    dlg._on_loaded(dlg._blame_bg())
    if dlg.table.rowCount() < 2:
        return
    target = dlg._lines[len(dlg._lines) - 1].content
    dlg.find_edit.setText(target)
    dlg.table.selectRow(0)
    dlg._find(True)
    assert dlg.table.currentRow() >= 0


def test_blame_dlg_view_toggles(qapp, git_repo, monkeypatch):
    """视图菜单：列显隐 / 忽略空白重载 / 检测档位，均不崩溃且持久化。"""
    from PySide6.QtCore import QSettings
    from pytortoisegit.dialogs import blamedlg as mod
    from pytortoisegit.blame import DETECT_MOVED_OR_COPIED_LINES_WITHIN_FILE

    QSettings("PyTortoiseGit", "PyTortoiseGit").clear()
    dlg = mod.BlameDlg(git_repo, "a.txt")
    dlg._on_loaded(dlg._blame_bg())
    assert dlg.table.isColumnHidden(dlg.COL_FILE)
    dlg.act_show_filename.trigger()
    assert not dlg.table.isColumnHidden(dlg.COL_FILE)
    dlg.act_show_log_id.trigger()
    assert not dlg.table.item(0, dlg.COL_COMMIT).text().startswith("0")
    dlg.act_ignore_ws.trigger()
    assert dlg._ignore_whitespace
    dlg._set_detect(DETECT_MOVED_OR_COPIED_LINES_WITHIN_FILE)
    assert dlg._detect == DETECT_MOVED_OR_COPIED_LINES_WITHIN_FILE
    dlg.close()
    QSettings("PyTortoiseGit", "PyTortoiseGit").clear()


# ---------------------------------------------------------------------------
# BrowseRefsDlg（菜单：检出所选引用）
# ---------------------------------------------------------------------------

def test_browse_refs_load_and_checkout(qapp, git_repo):
    from pytortoisegit.dialogs.browserefs import BrowseRefsDlg
    dlg = BrowseRefsDlg(git_repo)
    refs = dlg._load_bg()
    assert refs
    dlg._on_loaded(refs)
    top = dlg.tree.topLevelItem(0)
    assert top is not None and top.childCount() >= 1
    child = top.child(0)
    dlg.tree.setCurrentItem(child)
    full, rtype = dlg._selected()
    assert full and rtype == "branch"
    dlg._checkout_selected()
    assert dlg.current_branch
    # 未选中 → (None, None)，不会崩溃
    dlg.list.clearSelection()
    dlg.list.setCurrentItem(None)
    dlg.tree.setCurrentItem(None)
    assert dlg._selected() == (None, None)


def test_browse_refs_checkout_remote_message(qapp, git_repo, monkeypatch):
    from PySide6.QtWidgets import QMessageBox, QTreeWidgetItem
    from pytortoisegit.dialogs.browserefs import BrowseRefsDlg
    shown = {}
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: shown.setdefault("y", True)))
    dlg = BrowseRefsDlg(git_repo)
    item = QTreeWidgetItem(["origin/main"])
    item.setData(0, Qt.ItemDataRole.UserRole, "refs/remotes/origin/main")
    item.setData(0, Qt.ItemDataRole.UserRole + 1, "remote")
    dlg.tree.addTopLevelItem(item)
    dlg.tree.setCurrentItem(item)
    dlg._checkout_selected()
    assert shown.get("y")


# ---------------------------------------------------------------------------
# SelectRemoteRefDlg（Pulldlg 的“...”浏览器）
# ---------------------------------------------------------------------------

def test_select_remote_ref_accept(qapp, git_repo):
    from pytortoisegit.dialogs.selectremoterefdlg import SelectRemoteRefDlg
    dlg = SelectRemoteRefDlg(git_repo, remote="origin")
    dlg.remote_branch.addItem("origin/feature")
    dlg.remote_branch.setCurrentText("origin/feature")
    dlg.accept()
    assert dlg.selected == "origin/feature"
    assert dlg.result() == QDialog.DialogCode.Accepted


# ---------------------------------------------------------------------------
# MergeAbortDlg（合并冲突菜单：中止合并）
# ---------------------------------------------------------------------------

def test_merge_abort_reset(qapp, git_repo, auto_progress):
    from pytortoisegit.dialogs.mergeabortdlg import MergeAbortDlg
    dlg = MergeAbortDlg(git_repo)
    dlg.rd_hard.setChecked(True)
    dlg._on_abort()
    assert dlg.result() == QDialog.DialogCode.Accepted


# ---------------------------------------------------------------------------
# ResolveDlg（冲突解决）
# ---------------------------------------------------------------------------

def test_resolve_dlg_no_conflicts_and_actions(qapp, git_repo, monkeypatch):
    from pytortoisegit.dialogs.resolvedlg import ResolveDlg
    dlg = ResolveDlg(git_repo)
    # 无冲突 → 直接拒绝
    dlg._on_resolve()
    assert dlg.result() == QDialog.DialogCode.Rejected
    # 查看冲突：打开 DiffDlg
    opened = {}

    class _FakeDiff:
        def __init__(self, *a, **k):
            opened["y"] = True

        def show(self):
            pass

    monkeypatch.setattr("pytortoisegit.dialogs.diffdlg.DiffDlg", _FakeDiff)
    dlg._show_conflict("a.txt")
    assert opened.get("y")
    # 外部合并工具未配置：不崩溃
    dlg._launch_merge("a.txt")


def test_resolve_dlg_context_menu(qapp, git_repo, monkeypatch, auto_progress):
    from pytortoisegit.dialogs.resolvedlg import ResolveDlg
    from PySide6.QtWidgets import QTreeWidgetItem
    copied = {}

    class _FakeClip:
        def copy_text(self, text):
            copied["t"] = text

    monkeypatch.setattr("pytortoisegit.utils.clipboard.ClipboardHelper",
                        _FakeClip)
    monkeypatch.setattr("pytortoisegit.dialogs.diffdlg.DiffDlg",
                        type("D", (), {"__init__": lambda self, *a, **k: None,
                                       "show": lambda self: None}))
    dlg = ResolveDlg(git_repo)
    _menu, acts = dlg._build_menu()
    assert set(acts.values()) == {"open", "copy", "edit", "merge", "diff"}
    dlg._handle_menu("copy", "a.txt")
    assert copied["t"] == "a.txt"
    dlg._handle_menu("diff", "a.txt")     # 查看冲突
    # 标记解决：会 git add；用列表项模拟
    it = QTreeWidgetItem(["a.txt"])
    it.setData(0, Qt.ItemDataRole.UserRole, "a.txt")
    dlg.resolve_list.addTopLevelItem(it)
    dlg._handle_menu("edit", "a.txt")


# ---------------------------------------------------------------------------
# IgnoreDlg（未版本控制文件菜单：Ignore）
# ---------------------------------------------------------------------------

def test_ignore_dlg_writes_gitignore(qapp, git_repo):
    from pytortoisegit.dialogs.ignoredlg import IgnoreDlg
    target = Path(git_repo.root) / "new.txt"
    target.write_text("x\n", encoding="utf-8")
    dlg = IgnoreDlg(git_repo, paths=[str(target)])
    dlg.rd_local.setChecked(True)
    dlg._on_ignore()
    assert "new.txt" in (Path(git_repo.root) / ".gitignore").read_text(
        encoding="utf-8")
    assert dlg.result() == QDialog.DialogCode.Accepted


def test_ignore_dlg_recursive_and_exclude(qapp, git_repo):
    from pytortoisegit.dialogs.ignoredlg import IgnoreDlg
    sub = Path(git_repo.root) / "sub"
    sub.mkdir()
    target = sub / "gen.log"
    target.write_text("x\n", encoding="utf-8")
    dlg = IgnoreDlg(git_repo, paths=[str(target)])
    dlg.rd_recursive.setChecked(True)
    dlg.rd_exclude.setChecked(True)
    dlg._on_ignore()
    exclude = Path(git_repo.root) / ".git" / "info" / "exclude"
    assert "gen.log" in exclude.read_text(encoding="utf-8")
