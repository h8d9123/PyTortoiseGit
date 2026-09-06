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
    root = tmp_path_factory.mktemp("repo_a")
    runner = GitRunner(cwd=str(root))
    runner.init(str(root), initial_branch="main")
    repo = Repository.open(str(root))
    runner.run("config", "user.email", "t@example.com")
    runner.run("config", "user.name", "Tester")
    (root / "a.txt").write_text("line1\nline2\nline3\n", encoding="utf-8")
    runner.run("add", "-A")
    assert runner.run("commit", "-m", "initial").returncode == 0
    return repo

def _smoke(qapp, make, wait_ms=1500):
    from PySide6.QtCore import QTimer
    dlg = make()
    dlg.show()
    QTimer.singleShot(wait_ms, dlg.reject)
    dlg.exec()
    return dlg


def test_rename_dialog(qapp, repo):
    from pytortoisegit.dialogs.renamedlg import RenameDlg
    dlg = _smoke(qapp, lambda: RenameDlg(repo, ["a.txt"]))
    assert dlg.name_edit.text() == "a.txt"


def test_resolve_dialog(qapp, repo):
    from pytortoisegit.dialogs.resolvedlg import ResolveDlg
    dlg = _smoke(qapp, lambda: ResolveDlg(repo))
    assert dlg.resolve_list is not None


def test_commitisonrefs_dialog(qapp, repo):
    from pytortoisegit.dialogs.commitisonrefsdlg import CommitIsOnRefsDlg
    dlg = _smoke(qapp, lambda: CommitIsOnRefsDlg(repo, "HEAD"))
    assert dlg.subject_edit is not None


def test_cat_dialog(qapp, repo):
    from pytortoisegit.dialogs.catdlg import CatDlg
    dlg = _smoke(qapp, lambda: CatDlg(repo, "HEAD:a.txt"), wait_ms=1200)
    assert "line1" in dlg.view.toPlainText()


def test_conflicteditor_dialog(qapp, repo):
    from pytortoisegit.dialogs.conflicteditordlg import ConflictEditorDlg
    dlg = _smoke(qapp, lambda: ConflictEditorDlg(repo, "a.txt"))
    assert dlg.choice == "abort"


def test_autotext_dialog(qapp):
    from pytortoisegit.dialogs.autotexttestdlg import AutoTextTestDlg
    dlg = _smoke(qapp, lambda: AutoTextTestDlg(regex=r"\d+"))
    assert dlg.regex_edit.text() == r"\d+"


def test_command_registry_has_a_commands():
    from pytortoisegit.commands.dispatcher import available_commands, _ensure_imports
    _ensure_imports()
    cmds = available_commands()
    for expected in ("rename", "resolve", "cat", "cleanup", "help", "daemon",
                     "commitisonrefs", "conflicteditor", "autotexttest",
                     "repostatus", "stashsave", "stashpop", "stashlist",
                     "subsync", "unignore", "showcompare", "prevdiff"):
        assert expected in cmds