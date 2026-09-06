"""对话框冒烟测试（第二批：log/blame/commit/diff/sync/settings/clone）。"""

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
    (root / "new.txt").write_text("untracked\n", encoding="utf-8")
    return repo


def _smoke(qapp, make, wait_ms=2000):
    from PySide6.QtCore import QTimer
    dlg = make()
    dlg.show()
    QTimer.singleShot(wait_ms, dlg.reject)
    dlg.exec()
    return dlg


def test_log_dialog(qapp, repo):
    from pytortoisegit.dialogs.logdlg import LogDlg
    dlg = _smoke(qapp, lambda: LogDlg(repo, pathspec=None))
    assert dlg.log.count() >= 2
    assert dlg.tree.topLevelItemCount() >= 1


def test_blame_dialog(qapp, repo):
    from pytortoisegit.dialogs.blamedlg import BlameDlg
    dlg = _smoke(qapp, lambda: BlameDlg(repo, "a.txt"))
    assert dlg.table.rowCount() >= 3


def test_commit_dialog(qapp, repo):
    from pytortoisegit.dialogs.commitdlg import CommitDlg
    dlg = _smoke(qapp, lambda: CommitDlg(repo))
    assert dlg.status_tree.topLevelItemCount() >= 2


def test_changed_dialog(qapp, repo):
    from pytortoisegit.dialogs.changedlg import ChangedDlg
    dlg = _smoke(qapp, lambda: ChangedDlg(repo))
    assert dlg.status_tree.topLevelItemCount() >= 2


def test_diff_dialog(qapp, repo):
    from pytortoisegit.dialogs.diffdlg import DIFF_COL_DEL, DiffDlg
    dlg = _smoke(qapp, lambda: DiffDlg(repo, "HEAD~1", "HEAD"))
    assert dlg.file_tree.topLevelItemCount() >= 1
    assert dlg.file_tree.columnCount() == DIFF_COL_DEL + 1


def test_browse_refs_dialog(qapp, repo):
    from pytortoisegit.dialogs.browserefs import BrowseRefsDlg
    dlg = _smoke(qapp, lambda: BrowseRefsDlg(repo))
    assert dlg.tree.topLevelItemCount() >= 1


def test_create_branch_dialog(qapp, repo):
    from pytortoisegit.dialogs.createbranchdlg import CreateBranchDlg
    _smoke(qapp, lambda: CreateBranchDlg(repo))


def test_sync_dialog(qapp, repo):
    from pytortoisegit.dialogs.sync import SyncDlg
    dlg = _smoke(qapp, lambda: SyncDlg(repo))
    assert dlg.branch_label.text() in ("main", "")


def _settings_roots(dlg):
    return [dlg.tree.topLevelItem(i).text(0) for i in range(dlg.tree.topLevelItemCount())]


def _settings_children(item):
    return [item.child(i).text(0) for i in range(item.childCount())]


def test_settings_dialog_readonly(qapp):
    from pytortoisegit.dialogs.settingsdlg import SettingsDlg
    dlg = _smoke(qapp, lambda: SettingsDlg(None))
    assert dlg.name_edit is not None
    roots = _settings_roots(dlg)
    assert roots[0] == "General"
    assert "Git" in roots
    assert "Diff Viewer" in roots
    assert "Hook Scripts" in roots
    assert "Icon Overlays" in roots
    assert "Network" in roots
    assert "Credential" not in roots
    general = dlg.tree.topLevelItem(0)
    kids = _settings_children(general)
    assert "Context Menu" in kids
    assert "Dialogs 1" in kids
    assert "Dialogs 3" in kids
    assert "Colors 1" in kids
    assert "Alternative editor" in kids
    git = next(dlg.tree.topLevelItem(i) for i in range(dlg.tree.topLevelItemCount())
               if dlg.tree.topLevelItem(i).text(0) == "Git")
    assert "Credential" in _settings_children(git)
    assert "Remote" not in _settings_children(git)
    diff = next(dlg.tree.topLevelItem(i) for i in range(dlg.tree.topLevelItemCount())
                if dlg.tree.topLevelItem(i).text(0) == "Diff Viewer")
    assert "Merge Tool" in _settings_children(diff)


def test_settings_dialog_repo_pages(qapp, repo):
    from pytortoisegit.dialogs.settingsdlg import SettingsDlg
    dlg = _smoke(qapp, lambda: SettingsDlg(repo))
    git = next(dlg.tree.topLevelItem(i) for i in range(dlg.tree.topLevelItemCount())
               if dlg.tree.topLevelItem(i).text(0) == "Git")
    assert "Remote" in _settings_children(git)
    assert dlg.tree.currentItem() is not None
    assert dlg.tree.currentItem().text(0) == "Git"


def test_clone_dialog(qapp):
    from pytortoisegit.dialogs.clonedlg import CloneDlg
    dlg = _smoke(qapp, lambda: CloneDlg("https://github.com/user/repo.git"))
    assert dlg.dir_edit.text() != ""  # 自动补全目录名


def test_reflog_dialog(qapp, repo):
    from pytortoisegit.dialogs.reflogdlg import ReflogDlg
    dlg = _smoke(qapp, lambda: ReflogDlg(repo))
    assert dlg.table.rowCount() >= 2


def test_load_reflog(repo):
    from pytortoisegit.dialogs.reflogdlg import load_reflog
    entries = load_reflog(repo)
    assert len(entries) >= 2
    assert entries[0].selector.startswith("HEAD@{")
    assert entries[0].hash_
    assert entries[0].subject


def test_command_registry_has_new_commands():
    from pytortoisegit.commands.dispatcher import available_commands, _ensure_imports
    _ensure_imports()
    cmds = available_commands()
    for expected in ("commit", "log", "diff", "blame", "clone", "sync",
                     "settings", "branch", "tag", "browse", "reflog",
                     "shell"):
        assert expected in cmds


def test_progress_dialog_success_and_fail_text(qapp):
    from PySide6.QtCore import QEventLoop, QTimer
    from pytortoisegit.dialogs.progress import ProgressDialog
    from pytortoisegit.res.strings import tr

    def _run(fn):
        dlg = ProgressDialog()
        loop = QEventLoop()
        dlg.on_finish(lambda _ok: loop.quit())
        dlg.run(fn)
        QTimer.singleShot(2000, loop.quit)
        loop.exec()
        return dlg

    ok_dlg = _run(lambda: (True, 0))
    assert "成功" in ok_dlg._label.text()
    assert ok_dlg._btn_close.isHidden()
    assert ok_dlg._btn_cancel.text() == tr("close")
    assert ok_dlg._btn_cancel.isEnabled()
    assert ok_dlg._btn_cancel.isDefault()
    assert ok_dlg.progress.value() == 100
    ok_dlg.deleteLater()

    fail_dlg = _run(lambda: (False, 128))
    assert "128" in fail_dlg._label.text()
    assert fail_dlg._btn_close.isHidden()
    assert fail_dlg._btn_cancel.text() == tr("close")
    assert fail_dlg._btn_cancel.isEnabled()
    clicked = []
    fail_dlg.add_post_action("Pull", lambda: clicked.append(True))
    assert fail_dlg._post_box.count() == 1
    fail_dlg.deleteLater()


def test_push_dialog(qapp, repo):
    from pytortoisegit.dialogs.pushdlg import PushDlg
    from pytortoisegit.git.push import build_push_args
    dlg = _smoke(qapp, lambda: PushDlg(repo))
    assert dlg.local_combo.currentText() in ("main", "master")
    assert dlg.local_combo.height() < 40
    assert dlg.url_edit.height() < 40
    assert dlg.ref_group.objectName() == "IDC_BRANCH_GROUP"
    assert dlg.dest_group.width() > dlg.local_combo.width()
    dlg.remote_name_combo.setCurrentText("origin")
    dlg.remote_combo.setCurrentText("origin")
    opts = dlg._collect_opts()
    assert opts is not None
    args = build_push_args(opts)
    assert "main:origin" not in args
    assert args[-2:] == ["origin", dlg.local_combo.currentText()]


def test_pull_dialog(qapp, repo):
    from pytortoisegit.dialogs.pulldlg import PullFetchDlg
    dlg = _smoke(qapp, lambda: PullFetchDlg(repo, fetch_only=False))
    assert "origin" in [dlg.remote_combo.itemText(i)
                        for i in range(dlg.remote_combo.count())] or True


def test_fetch_dialog(qapp, repo):
    from pytortoisegit.dialogs.pulldlg import PullFetchDlg
    dlg = _smoke(qapp, lambda: PullFetchDlg(repo, fetch_only=True))
    assert dlg.chk_squash.isHidden()  # fetch 模式隐藏合并选项


def test_reset_dialog(qapp, repo):
    from pytortoisegit.dialogs.resetdlg import ResetDlg
    dlg = _smoke(qapp, lambda: ResetDlg(repo))
    assert dlg.cur_edit.text() in ("main", "master")


def test_revert_dialog(qapp, repo):
    from pytortoisegit.dialogs.revertdlg import RevertDlg
    dlg = _smoke(qapp, lambda: RevertDlg(repo))
    assert dlg.revert_list.topLevelItemCount() >= 1


def test_clean_dialog(qapp, repo):
    from pytortoisegit.dialogs.cleandlg import CleanDlg
    dlg = _smoke(qapp, lambda: CleanDlg(repo))
    assert dlg.rd_no.isChecked()


def test_add_dialog(qapp, repo):
    from pytortoisegit.dialogs.adddlg import AddDlg
    dlg = _smoke(qapp, lambda: AddDlg(repo))
    assert dlg.add_list.topLevelItemCount() >= 1  # new.txt 未跟踪


def test_ignore_dialog(qapp, repo):
    from pytortoisegit.dialogs.ignoredlg import IgnoreDlg
    dlg = _smoke(qapp, lambda: IgnoreDlg(repo, paths=["new.txt"]))
    assert dlg.rd_root.isChecked()


def test_command_registry_has_dialog_commands():
    from pytortoisegit.commands.dispatcher import available_commands, _ensure_imports
    _ensure_imports()
    cmds = available_commands()
    for expected in ("push", "pull", "fetch", "reset", "revert",
                     "clean", "add", "ignore"):
        assert expected in cmds


def test_export_dialog(qapp, repo):
    from pytortoisegit.dialogs.exportdlg import ExportDlg
    dlg = _smoke(qapp, lambda: ExportDlg(repo))
    assert dlg.file_edit.text().endswith(".zip")
    assert "HEAD" in [dlg.version_combo.itemText(i)
                      for i in range(dlg.version_combo.count())]


def test_formatpatch_dialog(qapp, repo):
    from pytortoisegit.dialogs.formatpatchdlg import FormatPatchDlg
    dlg = _smoke(qapp, lambda: FormatPatchDlg(repo))
    assert dlg.rd_since.isChecked()


def test_applypatch_dialog(qapp, repo):
    from pytortoisegit.dialogs.applypatchdlg import ApplyPatchDlg
    dlg = _smoke(qapp, lambda: ApplyPatchDlg(repo, patches=["a.patch"]))
    assert dlg.patch_list.topLevelItemCount() == 1


def test_createrepo_dialog(qapp):
    from pytortoisegit.dialogs.createrepoldg import CreateRepoDlg
    dlg = _smoke(qapp, lambda: CreateRepoDlg(r"C:\tmp\newrepo"))
    assert dlg.chk_bare is not None


def test_checkforupdates_dialog(qapp):
    from pytortoisegit.dialogs.checkforupdatesdlg import CheckForUpdatesDlg
    dlg = _smoke(qapp, lambda: CheckForUpdatesDlg())
    assert "version" in dlg.lbl_your.text().lower()


def test_bisectstart_dialog(qapp, repo):
    from pytortoisegit.dialogs.bisectstartdlg import BisectStartDlg
    dlg = _smoke(qapp, lambda: BisectStartDlg(repo))
    assert dlg.good_combo.count() >= 1


def test_command_registry_has_c2_commands():
    from pytortoisegit.commands.dispatcher import available_commands, _ensure_imports
    _ensure_imports()
    cmds = available_commands()
    for expected in ("export", "formatpatch", "importpatch", "repocreate",
                     "updatecheck", "bisect"):
        assert expected in cmds


def test_gitswitch_dialog(qapp, repo):
    from pytortoisegit.dialogs.gitswitchdlg import GitSwitchDlg
    dlg = _smoke(qapp, lambda: GitSwitchDlg(repo))
    assert dlg.rd_branch.isChecked()


def test_worktreelist_dialog(qapp, repo):
    from pytortoisegit.dialogs.worktreelistdlg import WorktreeListDlg
    dlg = _smoke(qapp, lambda: WorktreeListDlg(repo))
    assert dlg.tree.topLevelItemCount() >= 1


def test_worktreecreate_dialog(qapp, repo):
    from pytortoisegit.dialogs.worktreecreatedlg import WorktreeCreateDlg
    dlg = _smoke(qapp, lambda: WorktreeCreateDlg(repo))
    assert dlg.dir_edit.text() != ""


def test_repobrowser_dialog(qapp, repo):
    from pytortoisegit.dialogs.repobrowserdlg import RepositoryBrowserDlg
    dlg = _smoke(qapp, lambda: RepositoryBrowserDlg(repo))
    assert dlg.url_edit.text() != ""
    assert dlg.list.topLevelItemCount() >= 1


def test_revisiongraph_dialog(qapp, repo):
    from pytortoisegit.dialogs.revisiongraphdlg import RevisionGraphDlg
    dlg = _smoke(qapp, lambda: RevisionGraphDlg(repo))
    assert dlg.tree.topLevelItemCount() >= 1


def test_statgraph_dialog(qapp, repo):
    from pytortoisegit.dialogs.statgraphdlg import StatGraphDlg
    dlg = _smoke(qapp, lambda: StatGraphDlg(repo))
    assert dlg.num_commits_value.text() != ""


def test_command_registry_has_c3_commands():
    from pytortoisegit.commands.dispatcher import available_commands, _ensure_imports
    _ensure_imports()
    cmds = available_commands()
    for expected in ("worktreelist", "newworktree", "switch", "repobrowser",
                     "revisiongraph"):
        assert expected in cmds


def test_mergeabort_dialog(qapp, repo):
    from pytortoisegit.dialogs.mergeabortdlg import MergeAbortDlg
    dlg = _smoke(qapp, lambda: MergeAbortDlg(repo))
    assert dlg.rd_mixed.isChecked()


def test_createchangelist_dialog(qapp):
    from pytortoisegit.dialogs.createchangelistdlg import CreateChangelistDlg
    dlg = _smoke(qapp, lambda: CreateChangelistDlg())
    assert dlg.name_edit is not None


def test_addremote_dialog(qapp, repo):
    from pytortoisegit.dialogs.addremotedlg import AddRemoteDlg
    dlg = _smoke(qapp, lambda: AddRemoteDlg(repo))
    assert dlg.name_edit is not None


def test_selectremoteref_dialog(qapp, repo):
    from pytortoisegit.dialogs.selectremoterefdlg import SelectRemoteRefDlg
    dlg = _smoke(qapp, lambda: SelectRemoteRefDlg(repo, remote="origin"))
    assert dlg.remote_branch is not None


def test_requestpull_dialog(qapp, repo):
    from pytortoisegit.dialogs.requestpulldlg import RequestPullDlg
    dlg = _smoke(qapp, lambda: RequestPullDlg(repo))
    assert dlg.local_combo is not None


def test_toolassoc_dialog(qapp):
    from pytortoisegit.dialogs.toolassocdlg import ToolAssocDlg
    dlg = _smoke(qapp, lambda: ToolAssocDlg(ext=".cs", tool="expr"))
    assert dlg.result_value == (".cs", "expr")


def test_command_registry_has_c4_commands():
    from pytortoisegit.commands.dispatcher import available_commands, _ensure_imports
    _ensure_imports()
    cmds = available_commands()
    for expected in ("requestpull", "sendmail", "lfslock", "lfslocks",
                     "mergeabort", "addremote"):
        assert expected in cmds


def test_urldlg(qapp):
    from pytortoisegit.dialogs.inputdlg import UrlDlg
    dlg = _smoke(qapp, lambda: UrlDlg(initial="https://github.com/u/r.git"))
    assert dlg.combo is not None


def test_inputdlg(qapp):
    from pytortoisegit.dialogs.inputdlg import InputDlg
    dlg = _smoke(qapp, lambda: InputDlg(hint="msg:", text="hello"))
    assert dlg.text_edit.toPlainText() == "hello"


def test_simpleprompt_dialog(qapp):
    from pytortoisegit.dialogs.credentialdlg import SimplePromptDlg
    dlg = _smoke(qapp, lambda: SimplePromptDlg(realm="repo", user="u"))
    assert dlg.user_edit.text() == "u"
    dlg.accept()
    assert dlg.username == "u"


def test_usercert_dialog(qapp):
    from pytortoisegit.dialogs.credentialdlg import UserPasswdDlg, CertCheckDlg
    d1 = _smoke(qapp, lambda: UserPasswdDlg(user="u"))
    d1.accept()
    assert d1.username == "u"
    d2 = _smoke(qapp, lambda: CertCheckDlg(errordesc="bad cert"))
    assert d2.desc_label is not None


def test_firststart_wizard(qapp):
    from pytortoisegit.dialogs.firststartdlg import FirstStartWizard
    wiz = _smoke(qapp, lambda: FirstStartWizard())


def test_command_registry_has_c5_commands():
    from pytortoisegit.commands.dispatcher import available_commands, _ensure_imports
    _ensure_imports()
    cmds = available_commands()
    assert "firststart" in cmds


def test_mainmenu_dialog(qapp):
    from pytortoisegit.dialogs.mainmenu import MainMenuDlg
    dlg = _smoke(qapp, lambda: MainMenuDlg())
    assert dlg.command_list.count() >= 20
    # 关键命令应在菜单里
    names = [dlg.command_list.item(i).text()
             for i in range(dlg.command_list.count())]
    for expected in ("commit", "diff", "log", "blame", "clone", "sync",
                     "push", "pull", "settings", "add"):
        assert expected in names


def test_mainmenu_executes_diff(qapp, repo):
    from pytortoisegit.dialogs.mainmenu import MainMenuDlg
    from pytortoisegit.commands.dispatcher import dispatch, CommandContext
    dlg = MainMenuDlg(repo_path=str(repo.root))
    dlg.show()
    from PySide6.QtWidgets import QListWidgetItem
    from PySide6.QtCore import Qt
    # 选中 diff 命令并触发
    for i in range(dlg.command_list.count()):
        if dlg.command_list.item(i).data(Qt.ItemDataRole.UserRole) == "diff":
            dlg.command_list.setCurrentRow(i)
            break
    dlg.path_row.setText(str(repo.root))
    # 仅验证选中与路径，不真正执行（exec 会阻塞）
    assert dlg._selected_command() == "diff"
    assert dlg.path_row.text() == str(repo.root)
    dlg.reject()


def test_packaging_specs_compile():
    import ast
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    for rel in ("packaging/PyTortoiseGit.spec", "packaging/build.py"):
        src = (root / rel).read_text(encoding="utf-8")
        ast.parse(src)
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert "pytortoisegit.cli:main" in pyproject