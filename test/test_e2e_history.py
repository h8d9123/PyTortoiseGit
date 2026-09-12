"""E2E：日志/差异/Blame（TC-LOG / TC-DIFF / TC-BLAME）。

运行：QT_QPA_PLATFORM=offscreen python -m pytest test/test_e2e_history.py -v
"""

from pathlib import Path

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import QDialog


def _two_commits(repo):
    (Path(repo.root) / "a.txt").write_text("line1\nsecond\nline3\n", encoding="utf-8")
    repo.runner.run("add", "-A")
    repo.runner.run("commit", "-m", "second commit")
    return repo


def _log(ui, repo, **kw):
    from pytortoisegit.dialogs.logdlg import LogDlg
    dlg = LogDlg(repo, **kw)
    dlg.show()
    assert ui.wait_until(lambda: dlg.tree.topLevelItemCount() > 0), "日志未加载"
    return dlg


def test_TC_LOG_001_list_loads(qapp, ui, git_repo):
    """日志列表加载。"""
    _two_commits(git_repo)
    dlg = _log(ui, git_repo)
    assert dlg.tree.topLevelItemCount() == 2


def test_TC_LOG_002_author_search(qapp, ui, git_repo):
    """author: 搜索 → 仅该作者提交。"""
    _two_commits(git_repo)
    dlg = _log(ui, git_repo)
    ui.set_text(dlg.search_edit, "author:E2E")
    ui.key(dlg.search_edit, Qt.Key.Key_Return)
    assert ui.wait_until(lambda: dlg.tree.topLevelItemCount() == 2)


def test_TC_LOG_003_grep_search(qapp, ui, git_repo):
    """grep: 搜索 → 仅信息匹配提交。"""
    _two_commits(git_repo)
    dlg = _log(ui, git_repo)
    ui.set_text(dlg.search_edit, "grep:second")
    ui.key(dlg.search_edit, Qt.Key.Key_Return)
    assert ui.wait_until(lambda: dlg.tree.topLevelItemCount() == 1)
    assert "second" in dlg.tree.topLevelItem(0).text(2)


def test_TC_LOG_004_enter_does_not_close(qapp, ui, git_repo):
    """搜索回车不关闭对话框。"""
    _two_commits(git_repo)
    dlg = _log(ui, git_repo)
    ui.set_text(dlg.search_edit, "grep:initial")
    ui.key(dlg.search_edit, Qt.Key.Key_Return)
    ui.wait(200)
    assert dlg.result() != QDialog.DialogCode.Accepted
    assert dlg.isVisible()


def test_TC_LOG_005_date_filter(qapp, ui, git_repo):
    """日期范围过滤 → 范围外提交隐藏。"""
    _two_commits(git_repo)
    dlg = _log(ui, git_repo)
    future = QDate.currentDate().addYears(1)
    dlg.date_from.setDate(future)
    dlg.date_to.setDate(future)
    hidden = sum(1 for i in range(dlg.tree.topLevelItemCount())
                 if dlg.tree.topLevelItem(i).isHidden())
    assert hidden == dlg.tree.topLevelItemCount()


def test_TC_LOG_006_file_filter(qapp, ui, git_repo):
    """底部文件过滤 → 变更文件列表按关键词过滤。"""
    _two_commits(git_repo)
    dlg = _log(ui, git_repo)
    dlg.tree.setCurrentItem(dlg.tree.topLevelItem(0))
    dlg._on_commit_selected(dlg.tree.topLevelItem(0), 0)
    assert ui.wait_until(lambda: dlg.file_list.topLevelItemCount() > 0)
    ui.set_text(dlg.filter_edit, "zzz-no-match")
    hidden = sum(1 for i in range(dlg.file_list.topLevelItemCount())
                 if dlg.file_list.topLevelItem(i).isHidden())
    assert hidden == dlg.file_list.topLevelItemCount()


def test_TC_LOG_007_select_mode(qapp, ui, git_repo):
    """选择模式 → 返回所选提交 hash。"""
    _two_commits(git_repo)
    dlg = _log(ui, git_repo, select=True)
    dlg.tree.setCurrentItem(dlg.tree.topLevelItem(0))
    first = dlg.tree.topLevelItem(0).data(0, Qt.ItemDataRole.UserRole)
    ui.click(dlg.btn_ok)
    assert dlg.result() == QDialog.DialogCode.Accepted
    assert dlg.selected_hash == first


def test_TC_LOG_008_double_click_compare(qapp, ui, git_repo, monkeypatch):
    """双击提交 → 打开差异比较。"""
    _two_commits(git_repo)
    dlg = _log(ui, git_repo)
    seen = {}
    import pytortoisegit.dialogs.logdlg as mod

    class FakeDiff:
        def __init__(self, repo, rev1=None, rev2=None, paths=None, parent=None):
            seen.update(rev1=rev1, rev2=rev2)

        def exec(self):
            return 0

    monkeypatch.setattr(mod, "DiffDlg", FakeDiff)
    dlg._on_double_clicked(dlg.tree.topLevelItem(0), 0)
    assert seen.get("rev1") and seen.get("rev2")


def test_TC_DIFF_001_compare_commits(qapp, ui, git_repo):
    """比较两个提交 → 列出差异文件。"""
    _two_commits(git_repo)
    from pytortoisegit.dialogs.diffdlg import DiffDlg
    dlg = DiffDlg(git_repo, "HEAD~1", "HEAD")
    dlg.show()
    assert ui.wait_until(lambda: len(dlg.patches) > 0)
    assert dlg.file_tree.topLevelItemCount() > 0


def test_TC_DIFF_002_worktree_vs_head(qapp, ui, git_repo):
    """工作区与 HEAD 比较。"""
    (Path(git_repo.root) / "a.txt").write_text("dirty\n", encoding="utf-8")
    from pytortoisegit.dialogs.diffdlg import DiffDlg
    dlg = DiffDlg(git_repo, rev1="HEAD", rev2=None)
    dlg.show()
    assert ui.wait_until(lambda: len(dlg.patches) > 0)


def test_TC_BLAME_001_load(qapp, ui, git_repo):
    """Blame 按行显示归属。"""
    _two_commits(git_repo)
    from pytortoisegit.dialogs.blamedlg import BlameDlg
    dlg = BlameDlg(git_repo, "a.txt")
    dlg.show()
    assert ui.wait_until(lambda: dlg.table.rowCount() > 0)
