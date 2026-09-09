"""对话框冒烟测试（第三批：stash/merge/rebase/submodule/conflicts）。"""

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
    root = tmp_path_factory.mktemp("repo")
    runner = GitRunner(cwd=str(root))
    runner.init(str(root), initial_branch="main")
    repo = Repository.open(str(root))
    runner.run("config", "user.email", "t@example.com")
    runner.run("config", "user.name", "Tester")
    (root / "a.txt").write_text("line1\nline2\nline3\n", encoding="utf-8")
    runner.run("add", "-A")
    assert runner.run("commit", "-m", "initial").returncode == 0
    (root / "a.txt").write_text("line1\nmodified\nline3\n", encoding="utf-8")
    runner.run("add", "-A")
    assert runner.run("commit", "-m", "second").returncode == 0
    (root / "a.txt").write_text("line1\nmodified\nline3\nworking\n", encoding="utf-8")
    return repo


def _smoke(qapp, make, wait_ms=2500):
    from PySide6.QtCore import QTimer
    dlg = make()
    dlg.show()
    QTimer.singleShot(wait_ms, dlg.reject)
    dlg.exec()
    return dlg


def test_stash_dialog(qapp, repo):
    from pytortoisegit.dialogs.stashdlg import StashDlg
    dlg = _smoke(qapp, lambda: StashDlg(repo))
    assert dlg.msg_edit is not None
    assert dlg.untracked_box is not None
    assert dlg.all_box is not None


def test_merge_dialog(qapp, repo):
    from pytortoisegit.dialogs.mergedlg import MergeDlg
    dlg = _smoke(qapp, lambda: MergeDlg(repo))
    assert dlg.branch_combo.count() >= 0
    assert dlg.conflicts.tree is not None


def test_rebase_dialog(qapp, repo):
    from pytortoisegit.dialogs.rebasedlg import RebaseDlg
    dlg = _smoke(qapp, lambda: RebaseDlg(repo))
    assert dlg.branch_combo.count() >= 0


def test_submodule_dialog(qapp, repo):
    from pytortoisegit.dialogs.submoduledlg import SubmoduleDlg
    dlg = _smoke(qapp, lambda: SubmoduleDlg(repo))
    assert dlg.tree is not None


def test_conflicts_widget_with_conflict(qapp, tmp_path):
    runner = GitRunner(cwd=str(tmp_path))
    runner.init(str(tmp_path), initial_branch="main")
    rep = Repository.open(str(tmp_path))
    runner.run("config", "user.email", "t@example.com")
    runner.run("config", "user.name", "Tester")
    (tmp_path / "f.txt").write_text("base\n", encoding="utf-8")
    runner.run("add", "-A")
    runner.run("commit", "-m", "base", check=True)
    runner.run("checkout", "-b", "side", check=True)
    (tmp_path / "f.txt").write_text("side\n", encoding="utf-8")
    runner.run("commit", "-am", "side", check=True)
    runner.run("checkout", "main", check=True)
    (tmp_path / "f.txt").write_text("main\n", encoding="utf-8")
    runner.run("commit", "-am", "main", check=True)
    runner.run("merge", "side", check=False)

    from pytortoisegit.dialogs.conflicts import ConflictsWidget
    w = ConflictsWidget(rep)
    w.show()
    from PySide6.QtCore import QTimer
    QTimer.singleShot(1500, w.close)
    ok = False
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    deadline = 0
    poll = 0
    while poll < 200:
        app.processEvents()
        import time
        time.sleep(0.01)
        poll += 1
    w.close()
    assert w.tree.topLevelItemCount() == 1


def test_command_registry_includes_stage5():
    from pytortoisegit.commands.dispatcher import available_commands, _ensure_imports
    _ensure_imports()
    cmds = available_commands()
    for expected in ("stash", "merge", "rebase", "submodule",
                     "subupdate", "subadd"):
        assert expected in cmds