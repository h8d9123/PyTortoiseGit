"""更多对话框/组件的测试：ConflictsWidget / SubmoduleDlg / RebaseDlg / RegexFilterDlg。"""

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog


@pytest.fixture(autouse=True)
def _english_ui():
    from pytortoisegit.res import strings
    strings.set_language("en")
    yield
    strings.set_language("zh")


# ---------------------------------------------------------------------------
# RegexFilterDlg
# ---------------------------------------------------------------------------

def test_regex_filter_dlg(qapp):
    from pytortoisegit.merge.regexfilterdlg import RegexFilterDlg
    dlg = RegexFilterDlg(name="n", regex="r", replace="x")
    assert dlg.name_edit.text() == "n"
    assert dlg.regex_edit.text() == "r"
    dlg.name_edit.setText("n2")
    dlg.regex_edit.setText("r2")
    dlg.replace_edit.setText("y")
    dlg.accept()
    assert (dlg.m_sName, dlg.m_sRegex, dlg.m_sReplace) == ("n2", "r2", "y")
    assert dlg.result() == QDialog.DialogCode.Accepted


# ---------------------------------------------------------------------------
# ConflictsWidget
# ---------------------------------------------------------------------------

@pytest.fixture
def conflict_repo(git_repo):
    r = git_repo.runner
    root = Path(git_repo.root)
    r.run("checkout", "-b", "feature")
    (root / "a.txt").write_text("feature\n", encoding="utf-8")
    r.run("add", "-A")
    r.run("commit", "-m", "feature")
    r.run("checkout", "main")
    (root / "a.txt").write_text("main\n", encoding="utf-8")
    r.run("add", "-A")
    r.run("commit", "-m", "main")
    r.run("merge", "feature")            # 产生冲突
    return git_repo


def test_conflicts_widget_mark(qapp, conflict_repo):
    from pytortoisegit.dialogs.conflicts import ConflictsWidget
    w = ConflictsWidget(conflict_repo)
    assert w.count == 1
    w.tree.setCurrentItem(w.tree.topLevelItem(0))
    assert w._selected_path()
    w._on_mark()
    assert w.count == 0


def test_conflicts_widget_take_ours(qapp, conflict_repo):
    from pytortoisegit.dialogs.conflicts import ConflictsWidget
    w = ConflictsWidget(conflict_repo)
    w.tree.setCurrentItem(w.tree.topLevelItem(0))
    w._on_take("ours")
    assert w.count == 0
    assert (Path(conflict_repo.root) / "a.txt").read_text(
        encoding="utf-8") == "main\n"


def test_conflicts_widget_mark_all(qapp, conflict_repo):
    from pytortoisegit.dialogs.conflicts import ConflictsWidget
    w = ConflictsWidget(conflict_repo)
    w._on_mark_all()
    assert w.count == 0


def test_conflicts_widget_extmerge_warns(qapp, conflict_repo, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from pytortoisegit.dialogs.conflicts import ConflictsWidget
    from pytortoisegit.utils import externaltools
    # 隔离宿主机全局 git 配置（可能设置了 tortoisegit.externalmerge）
    monkeypatch.setattr(externaltools.DiffTool, "from_repo",
                        staticmethod(lambda repo: externaltools.DiffTool()))
    warned = {}
    monkeypatch.setattr(QMessageBox, "warning",
                        staticmethod(lambda *a, **k: warned.setdefault("y", True)))
    w = ConflictsWidget(conflict_repo)
    w.tree.setCurrentItem(w.tree.topLevelItem(0))
    w._on_extmerge()
    assert warned.get("y")


def test_conflicts_widget_menu(qapp, conflict_repo, monkeypatch):
    from pytortoisegit.dialogs.conflicts import ConflictsWidget
    copied = {}

    class _Clip:
        def copy_text(self, t):
            copied["t"] = t

    monkeypatch.setattr("pytortoisegit.utils.clipboard.ClipboardHelper", _Clip)
    w = ConflictsWidget(conflict_repo)
    _menu, acts = w._build_menu()
    assert set(acts.values()) == {"open", "copy", "ours", "theirs", "mark", "ext"}
    w._handle_menu("copy", "a.txt")
    assert copied["t"] == "a.txt"


# ---------------------------------------------------------------------------
# SubmoduleDlg
# ---------------------------------------------------------------------------

def test_submodule_dlg_loaded_and_menu(qapp, git_repo, monkeypatch):
    from pytortoisegit.dialogs.submoduledlg import SubmoduleDlg
    from pytortoisegit.git.submodule import SubmoduleEntry
    dlg = SubmoduleDlg(git_repo)
    dlg._on_loaded([SubmoduleEntry(path="sub", sha1="abc", status_char=" ")])
    assert dlg.tree.topLevelItemCount() == 1
    dlg.tree.setCurrentItem(dlg.tree.topLevelItem(0))
    assert dlg._selected_path() == "sub"
    _menu, acts = dlg._build_menu()
    assert set(acts.values()) == {"update", "sync", "deinit", "copy"}
    copied = {}

    class _Clip:
        def copy_text(self, t):
            copied["t"] = t

    monkeypatch.setattr("pytortoisegit.utils.clipboard.ClipboardHelper", _Clip)
    dlg._handle_menu("copy", "sub")
    assert copied["t"] == "sub"
    monkeypatch.setattr(dlg.sub, "deinit", lambda *a, **k: True)
    dlg._handle_menu("deinit", "sub")


def test_submodule_dlg_add(qapp, git_repo, monkeypatch):
    from PySide6.QtWidgets import QDialog
    from pytortoisegit.dialogs import submoduleadddlg
    from pytortoisegit.dialogs.submoduledlg import SubmoduleDlg

    class _FakeAdd:
        repository = "https://x/y.git"
        path = "y"
        branch = ""
        force = False
        putty_key = ""

        def __init__(self, *a, **k):
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(submoduleadddlg, "SubmoduleAddDlg", _FakeAdd)

    dlg = SubmoduleDlg(git_repo)
    added = {}
    monkeypatch.setattr(
        dlg.sub, "add",
        lambda path, url, force=False, branch=None:
        (added.setdefault("v", (path, url)), True)[1])
    dlg._on_add()
    assert added["v"] == ("y", "https://x/y.git")


def test_submodule_dlg_update_sync(qapp, git_repo, auto_progress, monkeypatch):
    from PySide6.QtWidgets import QDialog
    from pytortoisegit.dialogs import submoduleupdatedlg
    from pytortoisegit.dialogs.submoduledlg import SubmoduleDlg

    class _FakeUpdate:
        init = True
        recursive = True
        force = False
        no_fetch = False
        merge = False
        rebase = False
        remote = False
        paths = []
        all_selected = True

        def __init__(self, *a, **k):
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(submoduleupdatedlg, "SubmoduleUpdateDlg", _FakeUpdate)

    dlg = SubmoduleDlg(git_repo)
    monkeypatch.setattr(dlg.sub, "sync", lambda *a, **k: True)
    dlg.init_box.setChecked(True)
    dlg.recursive_box.setChecked(True)
    dlg._on_update()
    dlg._on_sync()


# ---------------------------------------------------------------------------
# RebaseDlg
# ---------------------------------------------------------------------------

@pytest.fixture
def rebase_repo(git_repo):
    r = git_repo.runner
    root = Path(git_repo.root)
    (root / "a.txt").write_text("m2\n", encoding="utf-8")
    r.run("add", "-A")
    r.run("commit", "-m", "m2")
    r.run("checkout", "-b", "feature")
    (root / "b.txt").write_text("f1\n", encoding="utf-8")
    r.run("add", "-A")
    r.run("commit", "-m", "f1")
    (root / "b.txt").write_text("f2\n", encoding="utf-8")
    r.run("add", "-A")
    r.run("commit", "-m", "f2")
    r.run("checkout", "main")
    return git_repo


def test_rebase_dlg_load_and_move(qapp, rebase_repo, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from pytortoisegit.dialogs.rebasedlg import RebaseDlg
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: None))
    dlg = RebaseDlg(rebase_repo)
    assert dlg.branch_combo.count() >= 2
    dlg.branch_combo.setCurrentText("feature")
    dlg.upstream_combo.setCurrentText("main")
    dlg._reload_commits()
    assert dlg.commit_list.topLevelItemCount() == 2
    first = dlg.commit_list.topLevelItem(0).data(0, Qt.ItemDataRole.UserRole)
    dlg.commit_list.setCurrentItem(dlg.commit_list.topLevelItem(0))
    dlg._move_commit(1)
    assert dlg.commit_list.topLevelItem(1).data(
        0, Qt.ItemDataRole.UserRole) == first
    dlg._on_reverse()
    assert dlg.branch_combo.currentText() == "main"
    assert dlg.upstream_combo.currentText() == "feature"


def test_rebase_dlg_continue_and_abort(qapp, rebase_repo, auto_progress, monkeypatch):
    from pytortoisegit.dialogs.rebasedlg import RebaseDlg
    dlg = RebaseDlg(rebase_repo, branch="feature")
    dlg.branch_combo.setCurrentText("feature")
    dlg.upstream_combo.setCurrentText("main")
    dlg._on_continue()
    dlg._on_abort()
    assert dlg.status.text()
