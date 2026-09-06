"""ChangedDlg 专项测试：行数据、复选框过滤、统计串、列头、几何。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from pytortoisegit.git.git import GitRunner
from pytortoisegit.git.repo import Repository


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def repo(tmp_path_factory):
    root = tmp_path_factory.mktemp("changedrepo")
    runner = GitRunner(cwd=str(root))
    runner.init(str(root), initial_branch="main")
    repo = Repository.open(str(root))
    runner.run("config", "user.email", "t@example.com")
    runner.run("config", "user.name", "Tester")
    (root / "mod.txt").write_text("l1\nl2\nl3\n", encoding="utf-8")
    (root / "del.txt").write_text("x\n", encoding="utf-8")
    (root / "add.txt").write_text("a1\na2\n", encoding="utf-8")
    runner.run("add", "-A")
    assert runner.run("commit", "-m", "initial").returncode == 0
    (root / "mod.txt").write_text("l1\nchanged\nl3\nl4\n", encoding="utf-8")
    runner.run("add", "-A")
    assert runner.run("commit", "-m", "second").returncode == 0
    # 工作区：改+删+未跟踪；仅暂存一个新增文件
    (root / "mod.txt").write_text("l1\nchanged\nl3\nl4\nwork\n", encoding="utf-8")
    (root / "del.txt").unlink()
    (root / "new.txt").write_text("n1\nn2\nn3\n", encoding="utf-8")
    (root / "staged.txt").write_text("s1\n", encoding="utf-8")
    runner.run("add", "staged.txt")
    return repo


def _run_dialog(qapp, make, wait_ms=1500):
    from PySide6.QtCore import QEventLoop, QTimer
    dlg = make()
    loop = QEventLoop()
    QTimer.singleShot(wait_ms, loop.quit)
    loop.exec()
    return dlg


def _row_texts(status_tree):
    out = []
    for i in range(status_tree.topLevelItemCount()):
        it = status_tree.topLevelItem(i)
        out.append([it.text(c) for c in range(it.columnCount() - 1)])
    return out


def test_changed_dialog_columns_and_rows(qapp, repo):
    from pytortoisegit.dialogs.changedlg import ChangedDlg
    dlg = _run_dialog(qapp, lambda: ChangedDlg(repo))
    assert dlg.status_tree.columnCount() == 6
    headers = [dlg.status_tree.headerItem().text(c) for c in range(6)]
    assert headers == ["Path", "Extension", "Status", "Lines added",
                       "Lines removed", "Last Modified"]
    paths = {r[0] for r in _row_texts(dlg.status_tree)}
    # 工作区：mod.txt 已修改、del.txt 已删除、new.txt 未跟踪、staged.txt 已暂存
    assert "mod.txt" in paths
    assert "del.txt" in paths
    assert "new.txt" in paths
    assert "staged.txt" in paths


def test_changed_dialog_actions_and_ext(qapp, repo):
    from pytortoisegit.dialogs.changedlg import ChangedDlg
    dlg = _run_dialog(qapp, lambda: ChangedDlg(repo))
    rows = _row_texts(dlg.status_tree)
    by_path = {r[0]: r for r in rows}
    assert by_path["mod.txt"][1] == "txt"
    assert by_path["mod.txt"][2] == "Modified"
    assert by_path["del.txt"][2] == "Deleted"
    assert by_path["new.txt"][2] == "non-versioned"
    assert by_path["staged.txt"][2] == "Added"
    assert by_path["mod.txt"][3] == "1"       # +1 行
    assert by_path["new.txt"][3] == "3"       # 未跟踪按行数


def test_changed_dialog_show_flags_filter(qapp, repo):
    from pytortoisegit.dialogs.changedlg import ChangedDlg
    dlg = _run_dialog(qapp, lambda: ChangedDlg(repo))
    # 关掉 unversioned：new.txt 消失
    dlg.chk_unversioned.setChecked(False)
    paths = {r[0] for r in _row_texts(dlg.status_tree)}
    assert "new.txt" not in paths
    assert "mod.txt" in paths
    # 重新打开
    dlg.chk_unversioned.setChecked(True)
    paths = {r[0] for r in _row_texts(dlg.status_tree)}
    assert "new.txt" in paths


def test_changed_dialog_statistics(qapp, repo):
    from pytortoisegit.dialogs.changedlg import ChangedDlg
    dlg = _run_dialog(qapp, lambda: ChangedDlg(repo))
    text = dlg.info_label.toPlainText()
    assert "line: 5(+) 1(-)" in text   # mod+1, new+3, staged+1 | del-1
    assert "modified=1" in text
    assert "deleted=1" in text
    assert "non-versioned=1" in text
    assert "added=1" in text          # staged.txt
    # IDC_SUMMARYTEXT 保持空白（m_pStatLabel 仅 CommitDlg）
    assert dlg.summary_text.text() == ""


def test_changed_dialog_title_and_layout(qapp, repo):
    from pytortoisegit.dialogs.changedlg import ChangedDlg
    dlg = _run_dialog(qapp, lambda: ChangedDlg(repo))
    assert dlg.windowTitle().endswith("Working Tree")
    assert dlg.windowTitle().startswith(repo.root)
    # 整仓默认：Whole Project 被禁用
    assert not dlg.chk_whole_project.isEnabled()
    assert dlg.chk_whole_project.isChecked()


def test_changed_dialog_whole_project_disabled(qapp, repo):
    from pytortoisegit.dialogs.changedlg import ChangedDlg
    dlg = _run_dialog(qapp, lambda: ChangedDlg(repo))
    assert not dlg.chk_whole_project.isEnabled()


def test_changed_dialog_branch_link(qapp, repo):
    from pytortoisegit.dialogs.changedlg import ChangedDlg
    dlg = _run_dialog(qapp, lambda: ChangedDlg(repo))
    assert "main" in dlg.branch_link.text()