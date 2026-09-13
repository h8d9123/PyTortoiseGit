"""差异视图与状态列表右键菜单的测试（对齐 CFileDiffDlg / CGitStatusListCtrl 菜单）。

规划用例：
  TC-DIFFMENU-001..008  DiffDlg 文件右键菜单
  TC-STATUSMENU-001..012 statusmenu 文件右键菜单（git 管理 / 未版本控制）
"""

from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt


@pytest.fixture(autouse=True)
def _english_ui():
    from pytortoisegit.res import strings
    strings.set_language("en")
    yield
    strings.set_language("zh")


def _trigger_file_menu(dlg, p, text, is_dir=False):
    """按文本选中 DiffDlg 文件菜单项并执行对应动作（模拟用户点击）。"""
    _menu, acts = dlg._build_file_menu(p, is_dir)
    for act, key in acts.items():
        if act.text() == text:
            dlg._handle_file_menu(key, p)
            return
    raise AssertionError(f"menu item not found: {text}")


def _fake_patch(path="a.txt"):
    return SimpleNamespace(git_path=path, raw="diff --git a/x b/x\n",
                           filename_display=path)


def _diff_dlg_with_item(monkeypatch, git_repo, path="a.txt"):
    from PySide6.QtWidgets import QTreeWidgetItem
    from pytortoisegit.dialogs import diffdlg as dd
    monkeypatch.setattr(dd, "run_async", lambda *a, **k: None)
    dlg = dd.DiffDlg(git_repo, "HEAD~1", "HEAD")
    item = QTreeWidgetItem([path])
    item.setData(0, Qt.ItemDataRole.UserRole, _fake_patch(path))
    dlg.file_tree.addTopLevelItem(item)
    item.setSelected(True)
    return dlg, item


def _status_action(menu, key, default):
    from pytortoisegit.res.strings import tr
    text = tr(key, default)
    for a in menu.actions():
        if a.text() == text:
            return a
    raise AssertionError(f"menu item not found: {text}")


# ---------------------------------------------------------------------------
# TC-DIFFMENU：DiffDlg 文件右键菜单
# ---------------------------------------------------------------------------

def test_diffmenu_items_present(qapp, git_repo, monkeypatch):
    """TC-DIFFMENU-001 菜单项齐全（文件）。"""
    dlg, item = _diff_dlg_with_item(monkeypatch, git_repo)
    p = item.data(0, Qt.ItemDataRole.UserRole)
    _menu, acts = dlg._build_file_menu(p, False)
    texts = [a.text() for a in acts]
    for t in ("Compare two revisions", "Show unified diff", "Revert to HEAD~1",
              "Revert to HEAD", "Show log", "Blame", "Export",
              "Save list...", "Copy path", "Copy extended path"):
        assert t in texts, texts


def test_diffmenu_compare_two_revisions(qapp, git_repo, monkeypatch):
    """TC-DIFFMENU-002 右键“Compare two revisions”打开并排比较。"""
    opened = {}

    class _FakeFrm:
        def __init__(self, *a, **k):
            opened["yes"] = True

        def show(self):
            pass

    monkeypatch.setattr("pytortoisegit.merge.mergefrm.MergeFrm", _FakeFrm)
    from pytortoisegit.dialogs import diffdlg as dd
    monkeypatch.setattr(dd.DiffDlg, "_use_external_diff",
                        staticmethod(lambda: False))
    dlg, item = _diff_dlg_with_item(monkeypatch, git_repo)
    p = item.data(0, Qt.ItemDataRole.UserRole)
    _trigger_file_menu(dlg, p, "Compare two revisions")
    assert opened.get("yes")


def test_diffmenu_show_unified_diff(qapp, git_repo, monkeypatch):
    """TC-DIFFMENU-003 右键“Show unified diff”显示补丁。"""
    dlg, item = _diff_dlg_with_item(monkeypatch, git_repo)
    p = item.data(0, Qt.ItemDataRole.UserRole)
    called = {}
    monkeypatch.setattr(dlg, "_show_patch", lambda x: called.setdefault("p", x))
    _trigger_file_menu(dlg, p, "Show unified diff")
    assert called.get("p") is not None


def test_diffmenu_show_log(qapp, git_repo, monkeypatch):
    """TC-DIFFMENU-004 右键“Show log”打开日志对话框。"""
    opened = {}

    class _FakeLog:
        def __init__(self, *a, **k):
            opened["yes"] = True

        def exec(self):
            return 0

    monkeypatch.setattr("pytortoisegit.dialogs.logdlg.LogDlg", _FakeLog)
    dlg, item = _diff_dlg_with_item(monkeypatch, git_repo)
    p = item.data(0, Qt.ItemDataRole.UserRole)
    _trigger_file_menu(dlg, p, "Show log")
    assert opened.get("yes")


def test_diffmenu_blame(qapp, git_repo, monkeypatch):
    """TC-DIFFMENU-005 右键“Blame”打开追溯对话框。"""
    opened = {}

    class _FakeBlame:
        def __init__(self, *a, **k):
            opened["yes"] = True

        def exec(self):
            return 0

    monkeypatch.setattr("pytortoisegit.dialogs.blamedlg.BlameDlg", _FakeBlame)
    dlg, item = _diff_dlg_with_item(monkeypatch, git_repo)
    p = item.data(0, Qt.ItemDataRole.UserRole)
    _trigger_file_menu(dlg, p, "Blame")
    assert opened.get("yes")


def test_diffmenu_revert_to_rev(qapp, git_repo, monkeypatch):
    """TC-DIFFMENU-006 右键“Revert to HEAD”：还原文件到该修订。"""
    from pathlib import Path
    from PySide6.QtWidgets import QMessageBox
    (Path(git_repo.root) / "a.txt").write_text("changed\n", encoding="utf-8")
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    dlg, item = _diff_dlg_with_item(monkeypatch, git_repo)
    p = item.data(0, Qt.ItemDataRole.UserRole)
    _trigger_file_menu(dlg, p, "Revert to HEAD")
    assert (Path(git_repo.root) / "a.txt").read_text(
        encoding="utf-8") == "line1\nline2\nline3\n"


def test_diffmenu_export(qapp, git_repo, monkeypatch, tmp_path):
    """TC-DIFFMENU-007 右键“Export”导出所选文件。"""
    from PySide6.QtWidgets import QFileDialog
    dest = tmp_path / "out.txt"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName",
        staticmethod(lambda *a, **k: (str(dest), "")))
    dlg, item = _diff_dlg_with_item(monkeypatch, git_repo)
    p = item.data(0, Qt.ItemDataRole.UserRole)
    _trigger_file_menu(dlg, p, "Export")
    assert dest.read_text(encoding="utf-8").startswith("line1")


def test_diffmenu_copy_path_and_extended(qapp, git_repo, monkeypatch):
    """TC-DIFFMENU-008 右键“Copy path / Copy extended path”写剪贴板。"""
    copied = {}

    class _FakeClip:
        def copy_text(self, text):
            copied["text"] = text

    monkeypatch.setattr("pytortoisegit.utils.clipboard.ClipboardHelper",
                        _FakeClip)
    dlg, item = _diff_dlg_with_item(monkeypatch, git_repo)
    p = item.data(0, Qt.ItemDataRole.UserRole)
    _trigger_file_menu(dlg, p, "Copy path")
    assert copied["text"] == "a.txt"
    _trigger_file_menu(dlg, p, "Copy extended path")
    assert copied["text"] == "a.txt"


# ---------------------------------------------------------------------------
# TC-STATUSMENU：状态列表右键菜单
# ---------------------------------------------------------------------------

def _menu(git_repo, path, on_refresh=None):
    from PySide6.QtWidgets import QWidget
    from pytortoisegit.dialogs.statusmenu import build_status_menu
    owner = QWidget()
    menu = build_status_menu(owner, git_repo, path, on_refresh=on_refresh)
    menu._owner = owner      # 保持父对象存活，避免菜单被 GC 删除
    return menu


def test_statusmenu_unversioned_add(qapp, git_repo):
    """TC-STATUSMENU-001 未版本控制文件：Add 后进入暂存区。"""
    from pathlib import Path
    (Path(git_repo.root) / "new.txt").write_text("n\n", encoding="utf-8")
    _status_action(_menu(git_repo, "new.txt"), "statusmenu_add", "Add").trigger()
    staged = git_repo.runner.run("diff", "--cached", "--name-only").stdout
    assert "new.txt" in staged


def test_statusmenu_versioned_revert(qapp, git_repo, monkeypatch):
    """TC-STATUSMENU-002 已管理文件：Revert 还原改动。"""
    from pathlib import Path
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    (Path(git_repo.root) / "a.txt").write_text("changed\n", encoding="utf-8")
    _status_action(_menu(git_repo, "a.txt"),
                   "statusmenu_revert", "Revert...").trigger()
    assert (Path(git_repo.root) / "a.txt").read_text(
        encoding="utf-8") == "line1\nline2\nline3\n"


def test_statusmenu_skip_worktree(qapp, git_repo):
    """TC-STATUSMENU-003 Skip worktree 生效。"""
    _status_action(_menu(git_repo, "a.txt"),
                   "statusmenu_skipworktree", "Skip worktree").trigger()
    out = git_repo.runner.run("ls-files", "-v", "--", "a.txt").stdout
    assert out.strip().startswith("S")     # S = skip-worktree


def test_statusmenu_assume_unchanged(qapp, git_repo):
    """TC-STATUSMENU-004 Assume Unchanged 生效。"""
    _status_action(_menu(git_repo, "a.txt"),
                   "statusmenu_assumevalid", "Assume Unchanged").trigger()
    out = git_repo.runner.run("ls-files", "-v", "--", "a.txt").stdout
    assert out.strip()[0].islower()        # h = assume-unchanged


def test_statusmenu_unversioned_delete(qapp, git_repo, monkeypatch):
    """TC-STATUSMENU-005 未版本控制文件：Delete 删除文件。"""
    from pathlib import Path
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    target = Path(git_repo.root) / "new.txt"
    target.write_text("n\n", encoding="utf-8")
    _status_action(_menu(git_repo, "new.txt"),
                   "statusmenu_delete", "Delete").trigger()
    assert not target.exists()


def test_statusmenu_commit_opens_dialog(qapp, git_repo, monkeypatch):
    """TC-STATUSMENU-006 Commit... 打开提交对话框。"""
    opened = {}

    class _FakeCommit:
        def __init__(self, *a, **k):
            opened["yes"] = True

        def exec(self):
            return 0

    monkeypatch.setattr("pytortoisegit.dialogs.commitdlg.CommitDlg", _FakeCommit)
    _status_action(_menu(git_repo, "a.txt"),
                   "statusmenu_commit", "Commit...").trigger()
    assert opened.get("yes")


def test_statusmenu_ignore_opens_dialog(qapp, git_repo, monkeypatch):
    """TC-STATUSMENU-007 未版本控制文件：Ignore 打开忽略对话框。"""
    from pathlib import Path
    opened = {}

    class _FakeIgnore:
        def __init__(self, *a, **k):
            opened["yes"] = True

        def exec(self):
            return 0

    monkeypatch.setattr("pytortoisegit.dialogs.ignoredlg.IgnoreDlg", _FakeIgnore)
    (Path(git_repo.root) / "new.txt").write_text("n\n", encoding="utf-8")
    _status_action(_menu(git_repo, "new.txt"),
                   "statusmenu_ignore", "Ignore").trigger()
    assert opened.get("yes")


def test_statusmenu_show_log_blame(qapp, git_repo, monkeypatch):
    """TC-STATUSMENU-008/009 Show log / Blame 打开对应对话框。"""
    from pathlib import Path
    opened = {}

    class _FakeLog:
        def __init__(self, *a, **k):
            opened["log"] = True

        def exec(self):
            return 0

    class _FakeBlame:
        def __init__(self, *a, **k):
            opened["blame"] = True

        def exec(self):
            return 0

    monkeypatch.setattr("pytortoisegit.dialogs.logdlg.LogDlg", _FakeLog)
    monkeypatch.setattr("pytortoisegit.dialogs.blamedlg.BlameDlg", _FakeBlame)
    (Path(git_repo.root) / "a.txt").write_text("x\n", encoding="utf-8")
    _status_action(_menu(git_repo, "a.txt"),
                   "statusmenu_log", "Show log").trigger()
    _status_action(_menu(git_repo, "a.txt"),
                   "statusmenu_blame", "Blame").trigger()
    assert opened.get("log") and opened.get("blame")


def test_statusmenu_export(qapp, git_repo, monkeypatch, tmp_path):
    """TC-STATUSMENU-010 Export 导出文件。"""
    from pathlib import Path
    from PySide6.QtWidgets import QFileDialog
    dest = tmp_path / "exp.txt"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName",
        staticmethod(lambda *a, **k: (str(dest), "")))
    (Path(git_repo.root) / "a.txt").write_text("hello\n", encoding="utf-8")
    _status_action(_menu(git_repo, "a.txt"),
                   "statusmenu_export", "Export selection to...").trigger()
    assert dest.read_text(encoding="utf-8") == "hello\n"


def test_statusmenu_copy_clipboard(qapp, git_repo, monkeypatch):
    """TC-STATUSMENU-011 复制到剪贴板子菜单各项。"""
    copied = {}

    class _FakeClip:
        def copy_text(self, text):
            copied["text"] = text

    monkeypatch.setattr("pytortoisegit.utils.clipboard.ClipboardHelper",
                        _FakeClip)
    menu = _menu(git_repo, "a.txt")
    from PySide6.QtWidgets import QMenu
    subs = menu.findChildren(QMenu)
    sub = next(s for s in subs
               if any(a.text() == "Relative path" for a in s.actions()))
    names = {a.text() for a in sub.actions()}
    assert "Full path" in names and "Relative path" in names
    assert "File name" in names and "Extended path" in names
    for a in sub.actions():
        if a.text() == "Relative path":
            a.trigger()
    assert copied["text"] == "a.txt"


def test_statusmenu_open_and_explore(qapp, git_repo, monkeypatch):
    """TC-STATUSMENU-012 Open / Explore 触发对应动作。"""
    calls = {}
    monkeypatch.setattr("pytortoisegit.dialogs.statusmenu._open",
                        lambda full: calls.setdefault("open", full))
    monkeypatch.setattr("pytortoisegit.dialogs.statusmenu._explore",
                        lambda full: calls.setdefault("explore", full))
    menu = _menu(git_repo, "a.txt")
    _status_action(menu, "statusmenu_open", "Open").trigger()
    _status_action(menu, "statusmenu_explore", "Explore to").trigger()
    assert calls.get("open") and calls.get("explore")
