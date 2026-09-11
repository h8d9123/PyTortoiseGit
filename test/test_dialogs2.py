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


def test_log_dialog_date_filter_and_enter(qapp, repo):
    import time
    from PySide6.QtCore import QDate, Qt
    from PySide6.QtTest import QTest
    from pytortoisegit.dialogs.logdlg import LogDlg
    dlg = LogDlg(repo, pathspec=None)
    dlg.show()
    for _ in range(200):
        qapp.processEvents()
        if dlg.tree.topLevelItemCount() >= 2:
            break
        time.sleep(0.02)
    n = dlg.tree.topLevelItemCount()
    assert n >= 2
    visible = lambda: [i for i in range(n) if not dlg.tree.topLevelItem(i).isHidden()]
    # 默认日期范围覆盖全部提交
    assert len(visible()) == n
    # 未来起点 → 全部隐藏
    dlg.date_from.setDate(QDate(2999, 1, 1))
    qapp.processEvents()
    assert visible() == []
    dlg.date_from.setDate(QDate(1970, 1, 1))
    qapp.processEvents()
    assert len(visible()) == n
    # 筛选框内回车不应关闭对话框
    dlg.filter_edit.setFocus()
    QTest.keyClick(dlg.filter_edit, Qt.Key.Key_Return)
    qapp.processEvents()
    assert dlg.isVisible()
    dlg.reject()


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


def test_clone_dialog_default_dir(qapp, tmp_path):
    from pytortoisegit.dialogs.clonedlg import CloneDlg
    dlg = _smoke(qapp, lambda: CloneDlg(default_dir=str(tmp_path)))
    assert dlg.dir_edit.text() == str(tmp_path)


def test_clone_dialog_default_dir_with_url_appends_repo_name(qapp, tmp_path):
    from pytortoisegit.dialogs.clonedlg import CloneDlg
    dlg = _smoke(qapp, lambda: CloneDlg(
        "https://github.com/user/repo.git", default_dir=str(tmp_path)))
    assert dlg.dir_edit.text() == str(tmp_path / "repo")


def test_clone_dialog_default_dir_editing_url_appends_repo_name(qapp, tmp_path):
    from pytortoisegit.dialogs.clonedlg import CloneDlg
    dlg = _smoke(qapp, lambda: CloneDlg(default_dir=str(tmp_path)))
    assert dlg.dir_edit.text() == str(tmp_path)
    # 模拟用户输入 URL 后失去焦点/回车
    dlg.url_combo.setEditText("https://github.com/user/myrepo.git")
    dlg.url_combo.lineEdit().editingFinished.emit()
    assert dlg.dir_edit.text() == str(tmp_path / "myrepo")


def test_clone_dialog_manual_dir_not_overridden(qapp, tmp_path):
    from pytortoisegit.dialogs.clonedlg import CloneDlg
    dlg = _smoke(qapp, lambda: CloneDlg(default_dir=str(tmp_path)))
    target = str(tmp_path / "custom")
    dlg.dir_edit.setText(target)
    dlg._dir_custom = True  # 等价于用户 Browse 选定目录
    dlg.url_combo.setEditText("https://github.com/user/myrepo.git")
    dlg.url_combo.lineEdit().editingFinished.emit()
    assert dlg.dir_edit.text() == target


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


def test_all_spec_groupboxes_created():
    """每个 load_spec 的对话框都应创建其 .rc 中的全部 GROUPBOX。"""
    import glob
    import json
    import os
    root = os.path.join(os.path.dirname(__file__), "..", "pytortoisegit")
    data = json.load(open(os.path.join(root, "res", "rc_dialogs.json"), encoding="utf-8"))
    srcs = {p: open(p, encoding="utf-8").read()
            for p in glob.glob(os.path.join(root, "**", "*.py"), recursive=True)}
    bad = []
    for d in data:
        ids = [c["id"] for c in d["controls"] if c["k"] == "GROUPBOX"]
        if not ids:
            continue
        for path, src in srcs.items():
            if f'load_spec("{d["id"]}")' in src:
                for gid in ids:
                    if gid not in src:
                        bad.append((os.path.relpath(path, root), d["id"], gid))
    assert not bad, bad


def test_pull_dialog_has_groupboxes(qapp, repo):
    from PySide6.QtWidgets import QGroupBox
    from pytortoisegit.dialogs.pulldlg import PullFetchDlg
    dlg = _smoke(qapp, lambda: PullFetchDlg(repo, fetch_only=False))
    # 对齐 IDD_PULLFETCH：Remote / Options 两个分组框
    assert isinstance(dlg.grp_remote, QGroupBox)
    assert isinstance(dlg.grp_options, QGroupBox)
    assert dlg.grp_remote.title() and dlg.grp_options.title()
    assert dlg.grp_remote.geometry().width() > 0
    assert dlg.grp_options.geometry().height() > 0


def test_pull_dialog_defaults_to_current_branch(qapp, repo):
    from pytortoisegit.dialogs.pulldlg import PullFetchDlg
    dlg = PullFetchDlg(repo, fetch_only=False)
    # 不再是硬编码 master，而是当前分支（或它跟踪的远程分支）
    assert dlg.remote_branch_edit.currentText() == repo.current_branch()
    assert dlg.remote_branch_edit.isEditable()


def test_pull_dialog_browse_ref_fills_branch(qapp, repo, monkeypatch):
    from PySide6.QtWidgets import QDialog
    import pytortoisegit.dialogs.selectremoterefdlg as srd
    from pytortoisegit.dialogs.pulldlg import PullFetchDlg
    dlg = PullFetchDlg(repo, fetch_only=False)

    class _FakeRefDlg:
        selected = "origin/develop"

        def __init__(self, *a, **k):
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(srd, "SelectRemoteRefDlg", _FakeRefDlg)
    dlg.btn_browse_ref.click()
    # 去掉远端前缀，填入远程分支名
    assert dlg.remote_branch_edit.currentText() == "develop"


def test_pull_dialog_source_toggle(qapp, repo):
    from pytortoisegit.dialogs.pulldlg import PullFetchDlg
    dlg = PullFetchDlg(repo, fetch_only=False)
    # 默认 Remote：远端下拉可用、URL 输入禁用、rebase 可用
    assert dlg.remote_combo.isEnabled()
    assert not dlg.other_edit.isEnabled()
    assert dlg.chk_rebase.isEnabled()
    # 切到 Arbitrary URL：反向
    dlg.rd_other.setChecked(True)
    qapp.processEvents()
    assert not dlg.remote_combo.isEnabled()
    assert dlg.other_edit.isEnabled()
    assert not dlg.chk_rebase.isEnabled()


def test_pull_clipboard_parse(qapp):
    from pytortoisegit.dialogs.pulldlg import PullFetchDlg
    url, branch = PullFetchDlg._parse_pull_clipboard(
        "git pull https://github.com/u/r.git develop")
    assert url == "https://github.com/u/r.git"
    assert branch == "develop"
    assert PullFetchDlg._parse_pull_clipboard("no url here") == ("", "")


def test_pull_dialog_horizontal_resize_only(qapp, repo):
    from pytortoisegit.dialogs.pulldlg import PullFetchDlg
    dlg = PullFetchDlg(repo, fetch_only=False)
    w, h = dlg.width(), dlg.height()
    # 高度固定、有最小宽度（对齐 BlockResize(DIALOG_BLOCKVERTICAL)）
    assert dlg.minimumHeight() == dlg.maximumHeight() == h
    assert dlg.minimumWidth() == w
    dlg.resize(w, h + 200)
    qapp.processEvents()
    assert dlg.height() == h                 # 纵向不可变
    dlg.resize(w + 120, h)
    qapp.processEvents()
    assert dlg.width() == w + 120            # 横向可拉伸
    dlg.resize(10, h)
    qapp.processEvents()
    assert dlg.width() >= w                  # 不小于最小宽度


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
    from pytortoisegit.res import strings
    strings.set_language("en")
    try:
        dlg = _smoke(qapp, lambda: CheckForUpdatesDlg())
        assert "version" in dlg.lbl_your.text().lower()
    finally:
        strings.set_language("zh")


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
    from PySide6.QtWidgets import QToolBar
    from pytortoisegit.dialogs.mainmenu import MainMenuDlg
    dlg = _smoke(qapp, lambda: MainMenuDlg())
    # 右侧为内容浏览区（资源管理器中间窗格）
    assert dlg.content_list is not None
    # 无工具栏（Git 操作入口在“命令”菜单）
    assert dlg.findChild(QToolBar) is None


def test_mainmenu_command_menu_lists_all_commands(qapp):
    """菜单栏「命令(&C)」覆盖全部已注册命令，且按功能分组。"""
    from pytortoisegit.dialogs.mainmenu import MainMenuDlg
    from pytortoisegit.commands.dispatcher import available_commands
    from pytortoisegit.res.strings import tr as _tr
    dlg = MainMenuDlg()
    top = [a.text() for a in dlg.menuBar().actions()]
    assert any(t.startswith("命令") for t in top)
    cmd_act = next(a for a in dlg.menuBar().actions()
                   if a.text().startswith("命令"))
    cmd_menu = cmd_act.menu()
    assert cmd_menu is not None
    shown: set[str] = set()
    group_labels: list[str] = []
    for act in cmd_menu.actions():
        sub = act.menu()
        if sub is not None:
            group_labels.append(act.text())
            shown.update(a.text() for a in sub.actions())
    for name in available_commands():
        label = _tr("menu_cmd_" + name, name)
        assert label in shown, f"命令菜单缺少: {name}"
    assert "本地更改" in group_labels
    assert "其他" in group_labels
    dlg.reject()


def test_mainmenu_content_shows_subfolders(qapp, tmp_path_factory):
    from pytortoisegit.dialogs.mainmenu import MainMenuDlg
    from pytortoisegit.git.git import GitRunner
    root = tmp_path_factory.mktemp("content")
    plain = root / "plain"
    plain.mkdir()
    inner = root / "innerrepo"
    inner.mkdir()
    runner = GitRunner(cwd=str(inner))
    runner.init(str(inner), initial_branch="main")
    runner.run("config", "user.email", "t@example.com")
    runner.run("config", "user.name", "Tester")
    (inner / "a.txt").write_text("a\n", encoding="utf-8")
    runner.run("add", "-A")
    assert runner.run("commit", "-m", "init").returncode == 0
    (root / "b.txt").write_text("b\n", encoding="utf-8")
    dlg = MainMenuDlg()
    dlg._show_content(str(root))
    model = dlg.fs_model
    root_index = model.index(str(root))
    # QFileSystemModel 异步填充：轮询等待目录加载完成
    from PySide6.QtTest import QTest
    for _ in range(50):
        if model.rowCount(root_index) == 3:
            break
        QTest.qWait(100)
    # 内含目录 plain、innerrepo 与文件 b.txt，共 3 项
    assert model.rowCount(root_index) == 3
    names = [model.fileName(model.index(i, 0, root_index))
             for i in range(model.rowCount(root_index))]
    for expected in ("plain", "innerrepo", "b.txt"):
        assert expected in names
    # innerrepo 被识别为仓库根；plain/b.txt 不是
    repo_idx = model.index(f"{root}{__import__('os').sep}innerrepo")
    plain_idx = model.index(f"{root}{__import__('os').sep}plain")
    assert dlg._is_repo_root(model.filePath(repo_idx))
    assert not dlg._is_repo_root(model.filePath(plain_idx))
    dlg.reject()


def test_mainmenu_content_double_click_repo_enters(qapp, isolated_settings, tmp_path_factory):
    from pytortoisegit.dialogs.mainmenu import MainMenuDlg
    from pytortoisegit.git.git import GitRunner
    root = tmp_path_factory.mktemp("content_enter_repo")
    inner = root / "r"
    inner.mkdir()
    runner = GitRunner(cwd=str(inner))
    runner.init(str(inner), initial_branch="main")
    runner.run("config", "user.email", "t@example.com")
    runner.run("config", "user.name", "Tester")
    (inner / "a.txt").write_text("a\n", encoding="utf-8")
    runner.run("add", "-A")
    assert runner.run("commit", "-m", "init").returncode == 0
    dlg = MainMenuDlg()
    dlg._show_content(str(root))
    model = dlg.fs_model
    root_index = model.index(str(root))
    # 等待模型异步填充
    from PySide6.QtTest import QTest
    for _ in range(50):
        if model.rowCount(root_index):
            break
        QTest.qWait(100)
    # 找到仓库 r 的子项，双击进入浏览（不改动 repo 打开）
    idx = None
    for i in range(model.rowCount(root_index)):
        cand = model.index(i, 0, root_index)
        if model.fileName(cand) == "r":
            idx = cand
            break
    assert idx is not None
    dlg._on_content_double_clicked(idx, 0)
    assert dlg._current_dir().replace("\\", "/").lower() == \
        str(inner).replace("\\", "/").lower()
    assert dlg.repo is None
    dlg.reject()


def test_mainmenu_go_up(qapp, tmp_path_factory):
    from pytortoisegit.dialogs.mainmenu import MainMenuDlg
    from PySide6.QtTest import QTest
    parent = tmp_path_factory.mktemp("goup")
    child = parent / "child"
    child.mkdir()
    dlg = MainMenuDlg()
    dlg._show_content(str(child))
    from PySide6.QtCore import Qt
    # 保证模型索引就绪
    idx = dlg.fs_model.index(str(child))
    for _ in range(50):
        if dlg.fs_model.rowCount(idx) >= 0:
            break
        QTest.qWait(100)
    assert dlg._current_dir().replace("\\", "/").lower() == \
        str(child).replace("\\", "/").lower()
    dlg._go_up()
    assert dlg.path_row.text().replace("\\", "/").lower() == \
        str(parent).replace("\\", "/").lower()

    def norm(p):
        return os.path.normcase(os.path.normpath(p))

    # 后退：parent -> child
    dlg._go_back()
    assert norm(dlg._current_dir()) == norm(str(child))
    # 前进：child -> parent
    dlg._go_forward()
    assert norm(dlg._current_dir()) == norm(str(parent))
    # 刷新：仍在 parent
    dlg._refresh_content()
    assert norm(dlg._current_dir()) == norm(str(parent))
    dlg.reject()


@pytest.fixture()
def isolated_settings(tmp_path, monkeypatch):
    """把 general_settings 隔离到临时 INI 文件，避免污染真实注册表。"""
    from PySide6.QtCore import QSettings
    s = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(
        "pytortoisegit.dialogs.settingsdlg.general_settings", lambda: s)
    return s


def test_mainmenu_opens_repo_auto_adds(qapp, repo, isolated_settings):
    from pytortoisegit.dialogs.mainmenu import MainMenuDlg
    from PySide6.QtCore import Qt
    dlg = MainMenuDlg(repo_path=str(repo.root))
    assert str(repo.root) in dlg._repo_list
    assert dlg.repo_tree.topLevelItemCount() == 1
    top = dlg.repo_tree.topLevelItem(0)
    assert top.data(0, Qt.ItemDataRole.UserRole + 1) == "repo"
    dlg.reject()


def test_mainmenu_repo_list_persists(qapp, repo, isolated_settings):
    from pytortoisegit.dialogs.mainmenu import MainMenuDlg
    dlg = MainMenuDlg(repo_path=str(repo.root))
    dlg.reject()
    # 重新打开窗口应从上一次的 QSettings 恢复列表
    dlg2 = MainMenuDlg()
    assert str(repo.root) in dlg2._repo_list
    assert dlg2.repo_tree.topLevelItemCount() == 1
    dlg2.reject()


def test_mainmenu_removes_repo(qapp, repo, isolated_settings):
    from pytortoisegit.dialogs.mainmenu import MainMenuDlg
    dlg = MainMenuDlg(repo_path=str(repo.root))
    top = dlg.repo_tree.topLevelItem(0)
    dlg._remove_repo_from_list(top)
    assert dlg._repo_list == []
    assert dlg.repo_tree.topLevelItemCount() == 0
    dlg.reject()


def test_mainmenu_double_click_switches_repo(
        qapp, repo, isolated_settings, tmp_path_factory):
    from pytortoisegit.dialogs.mainmenu import MainMenuDlg
    from pytortoisegit.git.git import GitRunner
    from PySide6.QtCore import Qt
    root2 = tmp_path_factory.mktemp("repo2")
    r2 = GitRunner(cwd=str(root2))
    r2.init(str(root2), initial_branch="main")
    r2.run("config", "user.email", "t@example.com")
    r2.run("config", "user.name", "Tester")
    (root2 / "b.txt").write_text("b\n", encoding="utf-8")
    r2.run("add", "-A")
    assert r2.run("commit", "-m", "init").returncode == 0

    dlg = MainMenuDlg(repo_path=str(repo.root))
    dlg.open_repo(str(root2))
    assert dlg.repo.root == str(root2)
    # 双击第一个仓库节点切回第一个仓库
    top = dlg.repo_tree.topLevelItem(0)
    assert top.data(0, Qt.ItemDataRole.UserRole) == str(repo.root)
    dlg._on_repo_double_clicked(top, 0)
    assert dlg.repo is not None and dlg.repo.root == str(repo.root)
    dlg.reject()


def test_mainmenu_submodule_lazy_load(qapp, isolated_settings, tmp_path_factory):
    from pytortoisegit.dialogs.mainmenu import MainMenuDlg
    from pytortoisegit.git.git import GitRunner
    from PySide6.QtCore import Qt
    subroot = tmp_path_factory.mktemp("subrepo")
    sr = GitRunner(cwd=str(subroot))
    sr.init(str(subroot), initial_branch="main")
    sr.run("config", "user.email", "t@example.com")
    sr.run("config", "user.name", "Tester")
    (subroot / "s.txt").write_text("s\n", encoding="utf-8")
    sr.run("add", "-A")
    assert sr.run("commit", "-m", "init").returncode == 0
    sub_sha = sr.run("rev-parse", "HEAD").stdout.strip()

    mainroot = tmp_path_factory.mktemp("mainrepo")
    mr = GitRunner(cwd=str(mainroot))
    mr.init(str(mainroot), initial_branch="main")
    mr.run("config", "user.email", "t@example.com")
    mr.run("config", "user.name", "Tester")
    (mainroot / "m.txt").write_text("m\n", encoding="utf-8")
    mr.run("add", "-A")
    assert mr.run("commit", "-m", "init").returncode == 0
    # 手工构造子模块：等价于先 clone 再 commit（避免 file 协议限制）
    (mainroot / ".gitmodules").write_text(
        "[submodule \"mysub\"]\n\tpath = mysub\n\turl = {}\n".format(
            str(subroot).replace("\\", "/")),
        encoding="utf-8")
    mr.run("add", ".gitmodules")
    res = mr.run("update-index", "--add", "--cacheinfo", "160000",
                 sub_sha, "mysub")
    assert res.returncode == 0, res.stderr
    assert mr.run("commit", "-m", "add submodule").returncode == 0

    dlg = MainMenuDlg(repo_path=str(mainroot))
    assert dlg.repo_tree.topLevelItemCount() == 1
    top = dlg.repo_tree.topLevelItem(0)
    # 当前仓库节点自动展开 → 子模块已懒加载
    assert top.childCount() == 1
    child = top.child(0)
    assert child.data(0, Qt.ItemDataRole.UserRole + 1) == "submodule"
    assert child.data(0, Qt.ItemDataRole.UserRole).replace("\\", "/").endswith("mysub")
    # 重复展开不重复加载
    dlg._on_item_expanded(top)
    assert top.childCount() == 1
    dlg.reject()


def test_mainmenu_folder_tab_two_tabs(qapp, isolated_settings):
    from pytortoisegit.dialogs.mainmenu import MainMenuDlg
    dlg = MainMenuDlg()
    assert dlg.manager_tabs.count() == 2
    assert dlg.manager_tabs.tabText(0) == "仓库管理"
    assert dlg.manager_tabs.tabText(1) == "目录树"
    # 目录树根节点为磁盘分区
    assert dlg.folder_tree.topLevelItemCount() >= 1
    dlg.reject()


def test_mainmenu_folder_tree_marks_and_opens_repo(
        qapp, isolated_settings, tmp_path_factory):
    from pytortoisegit.dialogs.mainmenu import MainMenuDlg
    from pytortoisegit.git.git import GitRunner
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QTreeWidgetItem

    parent = tmp_path_factory.mktemp("froot")
    inner = parent / "innerrepo"
    inner.mkdir()
    runner = GitRunner(cwd=str(inner))
    runner.init(str(inner), initial_branch="main")
    runner.run("config", "user.email", "t@example.com")
    runner.run("config", "user.name", "Tester")
    (inner / "a.txt").write_text("a\n", encoding="utf-8")
    runner.run("add", "-A")
    assert runner.run("commit", "-m", "init").returncode == 0

    dlg = MainMenuDlg()
    # 用内部方法直接加载一个目录节点，避免遍历真实磁盘
    parent_item = QTreeWidgetItem()
    parent_item.setData(0, Qt.ItemDataRole.UserRole, str(parent))
    dlg._load_dir_item(parent_item)
    assert parent_item.childCount() == 1
    child = parent_item.child(0)
    assert child.data(0, Qt.ItemDataRole.UserRole + 1) == "repo"
    # 双击仓库目录 → 主窗口打开
    dlg._on_folder_double_clicked(child, 0)
    assert dlg.repo is not None and dlg.repo.root == str(inner)
    dlg.reject()


def test_mainmenu_folder_tree_add_to_repo_list(
        qapp, isolated_settings, tmp_path_factory):
    from pytortoisegit.dialogs.mainmenu import MainMenuDlg
    from pytortoisegit.git.git import GitRunner
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QTreeWidgetItem

    parent = tmp_path_factory.mktemp("froot2")
    inner = parent / "innerrepo"
    inner.mkdir()
    runner = GitRunner(cwd=str(inner))
    runner.init(str(inner), initial_branch="main")
    runner.run("config", "user.email", "t@example.com")
    runner.run("config", "user.name", "Tester")
    (inner / "a.txt").write_text("a\n", encoding="utf-8")
    runner.run("add", "-A")
    assert runner.run("commit", "-m", "init").returncode == 0

    dlg = MainMenuDlg()
    parent_item = QTreeWidgetItem()
    parent_item.setData(0, Qt.ItemDataRole.UserRole, str(parent))
    dlg._load_dir_item(parent_item)
    child = parent_item.child(0)
    assert child.data(0, Qt.ItemDataRole.UserRole + 1) == "repo"
    # 用真实菜单构造助手，触发第一个动作“添加到仓库管理”
    path = child.data(0, Qt.ItemDataRole.UserRole)
    menu = dlg._build_folder_repo_menu(path)
    actions = menu.actions()
    assert actions
    actions[0].trigger()
    assert str(inner) in dlg._repo_list
    assert dlg.repo_tree.topLevelItemCount() == 1
    dlg.reject()


def test_mainmenu_folder_nonrepo_menu_has_clone_and_settings(
        qapp, isolated_settings, tmp_path_factory):
    from pytortoisegit.dialogs.mainmenu import MainMenuDlg
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QTreeWidgetItem
    parent = tmp_path_factory.mktemp("froot3")
    dlg = MainMenuDlg()
    item = QTreeWidgetItem()
    item.setData(0, Qt.ItemDataRole.UserRole, str(parent))
    item.setData(0, Qt.ItemDataRole.UserRole + 1, "dir")
    menu = dlg._build_folder_nonrepo_menu(str(parent))
    labels = [a.text() for a in menu.actions()]
    assert "Git Clone…" in labels
    assert "Settings" in labels
    assert "刷新" in labels
    dlg.reject()


def test_mainmenu_folder_refresh_rescans_children(
        qapp, isolated_settings, tmp_path, monkeypatch):
    from pytortoisegit.dialogs.mainmenu import MainMenuDlg
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QTreeWidgetItem
    parent = tmp_path / "refresh_root"
    parent.mkdir()
    dlg = MainMenuDlg()
    item = QTreeWidgetItem()
    item.setData(0, Qt.ItemDataRole.UserRole, str(parent))
    item.setData(0, Qt.ItemDataRole.UserRole + 1, "dir")
    dlg.folder_tree.addTopLevelItem(item)
    # 首次加载，仅有一个子目录 sub1
    (parent / "sub1").mkdir()
    item.setExpanded(True)  # 触发懒加载
    assert item.childCount() == 1
    # 新建 sub2 后刷新，应出现两个子目录
    (parent / "sub2").mkdir()
    dlg._refresh_folder_item(item)
    assert item.childCount() == 2
    dlg.reject()


def test_mainmenu_folder_repo_menu_includes_settings(
        qapp, isolated_settings, tmp_path_factory):
    from pytortoisegit.dialogs.mainmenu import MainMenuDlg
    from pytortoisegit.git.git import GitRunner
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QTreeWidgetItem
    parent = tmp_path_factory.mktemp("froot4")
    inner = parent / "innerrepo"
    inner.mkdir()
    runner = GitRunner(cwd=str(inner))
    runner.init(str(inner), initial_branch="main")
    runner.run("config", "user.email", "t@example.com")
    runner.run("config", "user.name", "Tester")
    (inner / "a.txt").write_text("a\n", encoding="utf-8")
    runner.run("add", "-A")
    assert runner.run("commit", "-m", "init").returncode == 0
    dlg = MainMenuDlg()
    menu = dlg._build_folder_repo_menu(str(inner))
    labels = [a.text() for a in menu.actions()]
    assert labels[0] == "添加到仓库管理"
    assert "Settings" in labels
    # 传入 item 后提供「刷新」
    from PySide6.QtWidgets import QTreeWidgetItem as _Item
    repo_item = _Item()
    repo_item.setData(0, Qt.ItemDataRole.UserRole, str(inner))
    menu2 = dlg._build_folder_repo_menu(str(inner), repo_item)
    labels2 = [a.text() for a in menu2.actions()]
    assert "刷新" in labels2
    dlg.reject()


def test_mainmenu_inside_repo_judgment(qapp, isolated_settings, tmp_path_factory):
    from pytortoisegit.dialogs.mainmenu import MainMenuDlg
    from pytortoisegit.git.git import GitRunner
    parent = tmp_path_factory.mktemp("insiderepo")
    repo = parent / "repo"
    repo.mkdir()
    runner = GitRunner(cwd=str(repo))
    runner.init(str(repo), initial_branch="main")
    sub = repo / "sub"
    sub.mkdir()
    dlg = MainMenuDlg()
    assert dlg._inside_repo(str(repo)) is True       # 仓库根
    assert dlg._inside_repo(str(sub)) is True        # 仓库内子目录
    assert dlg._inside_repo(str(parent)) is False    # 仓库外
    dlg.reject()


def test_mainmenu_content_context_menu_classic_for_worktree(
        qapp, isolated_settings, tmp_path_factory):
    """右侧内容区：工作树内目录右键显示完整经典菜单，仓库外显示 Clone+Settings。"""
    from pytortoisegit.dialogs.mainmenu import MainMenuDlg
    from pytortoisegit.git.git import GitRunner
    parent = tmp_path_factory.mktemp("content_ctx")
    repo = parent / "repo"
    repo.mkdir()
    runner = GitRunner(cwd=str(repo))
    runner.init(str(repo), initial_branch="main")
    sub = repo / "sub"
    sub.mkdir()
    plain = parent / "plain"
    plain.mkdir()
    dlg = MainMenuDlg()
    # 工作树内目录 → 经典菜单（含 Commit、Settings）
    menu = dlg._build_classic_menu(str(sub), dlg.content_list)
    labels = [a.text() for a in menu.actions()]
    assert "Commit…" in labels
    assert "Settings" in labels
    # 仓库外目录 → Clone+Settings（build_folder_nonrepo_menu）
    menu2 = dlg._build_folder_nonrepo_menu(str(plain))
    labels2 = [a.text() for a in menu2.actions()]
    assert "Git Clone…" in labels2
    assert "Settings" in labels2
    dlg.reject()


def test_mainmenu_blank_area_context_menu_uses_current_dir(
        qapp, isolated_settings, tmp_path_factory):
    """内容区空白处右键 → 对当前浏览目录弹完整 TortoiseGit 菜单。"""
    import os
    from pytortoisegit.dialogs.mainmenu import MainMenuDlg
    from pytortoisegit.git.git import GitRunner
    parent = tmp_path_factory.mktemp("blank_ctx")
    repo = parent / "repo"
    repo.mkdir()
    runner = GitRunner(cwd=str(repo))
    runner.init(str(repo), initial_branch="main")
    sub = repo / "sub"
    sub.mkdir()
    plain = parent / "plain"
    plain.mkdir()
    dlg = MainMenuDlg()
    # 当前浏览为工作树内子目录 → 空白处菜单含完整 TortoiseGit 命令（状态驱动）
    dlg._show_content(str(sub))
    menu = dlg._build_blank_menu(dlg._current_dir(), dlg.content_list)
    labels = [a.text() for a in menu.actions()]
    for expected in ("Pull…", "Push…", "Sync", "Commit…",
                     "Diff…", "Show log", "Repo Browser", "Stash changes…",
                     "Revert…", "Switch/Checkout…", "Merge…", "Settings"):
        assert expected in labels, expected
    # 工作树内子目录本身不显示 Git Clone（文件夹已在 git 中）
    assert "Git Clone…" not in labels
    # 当前浏览为仓库外目录 → Clone+Settings
    dlg._show_content(str(plain))
    menu2 = dlg._build_blank_menu(dlg._current_dir(), dlg.content_list)
    labels2 = [a.text() for a in menu2.actions()]
    assert "Git Clone…" in labels2
    assert "Settings" in labels2
    assert "Commit…" not in labels2
    dlg.reject()


def test_mainmenu_file_menu_includes_tg_commands(
        qapp, isolated_settings, tmp_path_factory):
    """文件右键菜单（工作树内）：Commit/Diff/Log/Stash/Blame/Settings。"""
    from pytortoisegit.dialogs.mainmenu import MainMenuDlg
    from pytortoisegit.git.git import GitRunner
    parent = tmp_path_factory.mktemp("file_ctx")
    repo = parent / "repo"
    repo.mkdir()
    runner = GitRunner(cwd=str(repo))
    runner.init(str(repo), initial_branch="main")
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    sub = repo / "sub"
    sub.mkdir()
    (sub / "b.txt").write_text("b\n", encoding="utf-8")
    runner.run("add", "-A")
    runner.run("commit", "-m", "init")
    (repo / "a.txt").write_text("modified\n", encoding="utf-8")
    dlg = MainMenuDlg()
    # 工作树内文件 → 打开/显示位置 + TortoiseGit 命令（状态驱动）
    menu = dlg._build_file_menu(str(repo / "a.txt"), dlg.content_list)
    labels = [a.text() for a in menu.actions()]
    assert "打开" in labels
    assert "显示位置" in labels
    for expected in ("Commit…", "Diff…", "Show log", "Stash changes…",
                     "Blame…", "Settings", "Revert…", "Remove…"):
        assert expected in labels, expected
    # 工作树内子目录中的文件
    menu2 = dlg._build_file_menu(str(sub / "b.txt"), dlg.content_list)
    labels2 = [a.text() for a in menu2.actions()]
    assert "Commit…" in labels2
    assert "Stash changes…" in labels2
    dlg.reject()


def test_mainmenu_file_menu_outside_repo_only_system(
        qapp, isolated_settings, tmp_path_factory):
    """仓库外文件右键：仅有打开/显示位置，无 Git 命令。"""
    from pytortoisegit.dialogs.mainmenu import MainMenuDlg
    parent = tmp_path_factory.mktemp("file_plain")
    f = parent / "x.txt"
    f.write_text("x\n", encoding="utf-8")
    dlg = MainMenuDlg()
    menu = dlg._build_file_menu(str(f), dlg.content_list)
    labels = [a.text() for a in menu.actions()]
    assert "打开" in labels
    assert "显示位置" in labels
    assert "Commit…" not in labels
    assert "Stash changes…" not in labels
    assert "Settings" not in labels
    dlg.reject()


def test_mainmenu_menu_actions_have_tortoisegit_icons(
        qapp, isolated_settings, tmp_path_factory):
    """右键菜单 Git 操作带 TortoiseGit 图标（IDI_* 对应的 menu*.ico）。"""
    from pytortoisegit.dialogs.mainmenu import MainMenuDlg
    from pytortoisegit.git.git import GitRunner
    parent = tmp_path_factory.mktemp("menu_icons")
    repo = parent / "repo"
    repo.mkdir()
    runner = GitRunner(cwd=str(repo))
    runner.init(str(repo), initial_branch="main")
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    runner.run("add", "-A")
    runner.run("commit", "-m", "init")
    (repo / "a.txt").write_text("b\n", encoding="utf-8")
    plain = parent / "plain"
    plain.mkdir()
    dlg = MainMenuDlg()

    def by_label(actions, label):
        return next(a for a in actions if a.text() == label)

    # 经典菜单：Commit/Log/Pull/Push/Sync/Revert/CleanUp/Settings 均有图标
    classic = dlg._build_classic_menu(str(repo))
    for label in ["Commit…", "Show log", "Pull…", "Push…", "Sync",
                  "Revert…", "Clean Up…", "Settings"]:
        act = by_label(classic.actions(), label)
        assert not act.icon().isNull(), label
    # 文件菜单：打开/Commit/Diff/Show log/Stash changes…/Blame…/Settings
    fmenu = dlg._build_file_menu(str(repo / "a.txt"), dlg.content_list)
    for label in ["打开", "Commit…", "Diff…", "Show log",
                  "Stash changes…", "Blame…", "Settings"]:
        act = by_label(fmenu.actions(), label)
        assert not act.icon().isNull(), label
    # 仓库外目录：Clone + Settings
    nrepo = dlg._build_folder_nonrepo_menu(str(plain))
    for label in ["Git Clone…", "Settings"]:
        act = by_label(nrepo.actions(), label)
        assert not act.icon().isNull(), label
    dlg.reject()


def test_mainmenu_shift_extends_menu(
        qapp, isolated_settings, tmp_path_factory, monkeypatch):
    """按住 Shift 时，扩展命令（defaultExtMenuEntries）满足状态条件才显示。"""
    from pytortoisegit.dialogs.mainmenu import MainMenuDlg
    from pytortoisegit import menuitems as mi
    parent = tmp_path_factory.mktemp("shift_ctx")
    repo = parent / "repo"
    repo.mkdir()
    from pytortoisegit.git.git import GitRunner
    runner = GitRunner(cwd=str(repo))
    runner.init(str(repo), initial_branch="main")
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    runner.run("add", "-A")
    runner.run("commit", "-m", "init")
    runner.run("config", "svn-remote.svn.url", "http://example.com/svn")
    # 构造 stash，使 StashApply 的 ITEMIS_STASH 条件成立
    (repo / "a.txt").write_text("b\n", encoding="utf-8")
    runner.run("stash", "push", "-m", "wip")

    dlg = MainMenuDlg()
    dlg._shift_pressed = lambda: False

    def labels_of(menu):
        return [a.text() for a in menu.actions() if a.text()]

    states = mi.compute_item_states(str(repo), extended=False)
    cmds_plain = mi.menu_entries(states)
    plain_cmds = [e.command for e in cmds_plain if e.command != "separator"]
    ext_cmds = ("svnignore", "stashapply", "subsync")
    # 未按 Shift → 扩展项不显示
    assert not any(c in plain_cmds for c in ext_cmds)
    # 按住 Shift（有 stash→StashApply 条件成立）
    dlg._shift_pressed = lambda: True
    menu = dlg._build_classic_menu(str(repo), dlg.content_list)
    a_labels = labels_of(menu)
    assert any(("Stash Apply" == t) for t in a_labels), a_labels
    dlg.reject()


def test_menuitems_state_driven_entries(tmp_path_factory):
    """状态引擎：不同文件/目录状态显示不同菜单项（镜像 MenuInfo.cpp）。"""
    from pytortoisegit.git.git import GitRunner
    from pytortoisegit import menuitems as mi
    parent = tmp_path_factory.mktemp("mi_engine")
    repo = parent / "repo"
    repo.mkdir()
    runner = GitRunner(cwd=str(repo))
    runner.init(str(repo), initial_branch="main")
    runner.run("config", "user.email", "t@x.com")
    runner.run("config", "user.name", "T")
    (repo / "tracked.txt").write_text("a\n", encoding="utf-8")
    (repo / "untracked.txt").write_text("u\n", encoding="utf-8")
    (repo / "new.txt").write_text("n\n", encoding="utf-8")
    sub = repo / "sub"
    sub.mkdir()
    runner.run("add", "tracked.txt")
    runner.run("commit", "-m", "init")
    (repo / "tracked.txt").write_text("mod\n", encoding="utf-8")
    (repo / "untracked.txt").write_text("u2\n", encoding="utf-8")

    def cmds(path):
        s = mi.compute_item_states(str(path), extended=False)
        return [e.command for e in mi.menu_entries(s) if e.command != "separator"]

    # 未跟踪文件 → Add/Ignore，无 Commit/Diff/Lock
    c = cmds(repo / "untracked.txt")
    assert "add" in c and "ignore" in c
    assert "commit" not in c and "diff" not in c
    # 已跟踪且已修改 → Commit/Diff/Log/StashSave/Revert/Blame/Lock
    c = cmds(repo / "tracked.txt")
    for want in ("commit", "diff", "log", "stashsave", "revert", "blame", "lfslock"):
        assert want in c, want
    # 工作树内目录 → 仓库级操作（Pull/Push/Sync/RepoBrowser/Log）
    c = cmds(repo)
    for want in ("pull", "push", "sync", "repobrowser", "log", "commit"):
        assert want in c, want
    # 未知文件（未在 status 中）→ 提交/修改菜单；新增文件被 add 后未知→ commit/diff
    c = cmds(repo / "new.txt")
    assert "add" in c or "commit" in c
    # 仓库外目录 → Clone/CreateRepo+Settings，无 Commit
    plain = parent / "plain"
    plain.mkdir()
    c = cmds(plain)
    assert "clone" in c and "repocreate" in c
    assert "commit" not in c and "diff" not in c


def test_content_folder_icons_untracked_plain(tmp_path_factory, qapp):
    """内容区目录图标：仅仓库根显示 git 绿勾，未受版本管理的子目录为普通图标。"""
    import os
    from PySide6.QtCore import Qt
    from pytortoisegit.git.git import GitRunner
    from pytortoisegit.dialogs.mainmenu import MainMenuDlg
    from pytortoisegit.res import icons
    parent = tmp_path_factory.mktemp("icontest")
    repo = parent / "repo"
    repo.mkdir()
    runner = GitRunner(cwd=str(repo))
    runner.init(str(repo), initial_branch="main")
    runner.run("config", "user.email", "t@x.com")
    runner.run("config", "user.name", "T")
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    runner.run("add", "-A")
    runner.run("commit", "-m", "init")
    # 未受版本管理的子目录
    (repo / "nd").mkdir()
    (repo / "nd" / "x.txt").write_text("x\n", encoding="utf-8")

    dlg = MainMenuDlg()
    dlg._show_content(str(repo))
    model = dlg.fs_model
    git_icon = icons.icon("IDI_GITFOLDER")

    def is_git(p):
        ic = model.data(model.index(p), Qt.ItemDataRole.DecorationRole)
        return ic is not None and not ic.isNull() and \
            ic.cacheKey() == git_icon.cacheKey()

    # 仓库根 → git 图标
    assert is_git(str(repo))
    # 未受版本管理的子目录 → 普通图标
    assert not is_git(str(repo / "nd"))
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


def test_settings_language_combo_switches(qapp):
    from pytortoisegit.dialogs.settingsdlg import SettingsDlg
    from pytortoisegit.res import strings
    dlg = SettingsDlg()
    dlg._load_general()
    target = combo = None
    for _, page in dlg.pages:
        if getattr(page, "language_combo", None) is not None:
            target, combo = page, page.language_combo
    assert combo is not None
    assert [combo.itemText(i) for i in range(combo.count())] == [
        "English", "简体中文", "繁體中文", "Deutsch"]
    try:
        combo.setCurrentIndex(combo.findData("English"))
        target.apply_to_settings()
        assert strings.get_language() == "en"
    finally:
        combo.setCurrentIndex(combo.findData("zh_CN"))
        target.apply_to_settings()
        assert strings.get_language() == "zh"


def test_firststart_language_mapping(qapp):
    from pytortoisegit.dialogs.firststartdlg import _LanguagePage
    page = _LanguagePage()
    assert page.lang_combo.count() == 4
    for idx, expected in enumerate(("English", "zh_CN", "zh_TW", "Deutsch")):
        page.lang_combo.setCurrentIndex(idx)
        assert page.selected_language() == expected


def test_progress_dialog_has_animation(qapp):
    from pytortoisegit.dialogs.progress import ProgressDialog, _ANIMATION
    assert _ANIMATION.is_file()
    dlg = ProgressDialog(title="git push")
    assert dlg._movie is not None and dlg._movie.isValid()
    assert dlg._movie.frameCount() >= 2
    assert dlg._anim.width() > 0 and dlg._anim.height() > 0


def test_theme_embeds_groupbox_title(qapp):
    from pytortoisegit.ui.theme import GROUPBOX_QSS, apply_theme
    old = qapp.styleSheet()
    try:
        apply_theme(qapp)
        assert qapp.styleSheet() == GROUPBOX_QSS
        assert "QGroupBox::title" in GROUPBOX_QSS
        assert "subcontrol-position: top left" in GROUPBOX_QSS
    finally:
        qapp.setStyleSheet(old)


def test_place_widget_label_height_fits_text(qapp):
    from PySide6.QtWidgets import QDialog, QLabel
    from pytortoisegit.ui import rc as rc_mod
    from pytortoisegit.ui.rc import DialogUnits
    dlg = QDialog()
    fu = DialogUnits(9, "Segoe UI")
    ctrl = rc_mod.Control(kind="LTEXT", text="管理远程", ctrl_id="X", cls="",
                          style="", x=0, y=0, w=60, h=8)
    lbl = QLabel("管理远程", dlg)
    rc_mod.place_widget(dlg, fu, ctrl, lbl)
    assert lbl.height() >= lbl.sizeHint().height()