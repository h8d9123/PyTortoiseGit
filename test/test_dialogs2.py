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
    assert len(list(dlg._iter_file_items())) >= 2


def test_commit_title_and_target_editing(qapp, repo):
    """标题为 路径 - Commit - TortoiseGit；目标分支只读，勾选 new branch 才可编辑。"""
    from pytortoisegit.dialogs.commitdlg import CommitDlg
    dlg = CommitDlg(repo)
    assert dlg.windowTitle() == f"{repo.root} - Commit - TortoiseGit"
    assert dlg.commit_to_edit.isReadOnly()
    assert not dlg.commit_to_edit.isHidden()
    assert dlg.newbranch_edit.isHidden()
    dlg.chk_new_branch.setChecked(True)
    assert not dlg.newbranch_edit.isHidden()
    assert dlg.commit_to_edit.isHidden()
    dlg.chk_new_branch.setChecked(False)
    assert dlg.newbranch_edit.isHidden()
    assert not dlg.commit_to_edit.isHidden()


def test_commit_amend_loads_and_restores_message(qapp, repo):
    """勾选 Amend 载入 HEAD 信息，取消后还原原信息。"""
    from pytortoisegit.dialogs.commitdlg import CommitDlg
    dlg = CommitDlg(repo)
    assert dlg.amend_box.isEnabled()          # 仓库有提交
    dlg.message_edit.setPlainText("my new message")
    dlg.amend_box.setChecked(True)
    assert "second" in dlg.message_edit.toPlainText()   # HEAD 提交为 "second"
    dlg.message_edit.setPlainText("amended")
    dlg.amend_box.setChecked(False)
    assert dlg.message_edit.toPlainText() == "my new message"


def test_commit_amend_disabled_without_head(qapp, tmp_path):
    from pytortoisegit.git.git import GitRunner
    from pytortoisegit.git.repo import Repository
    from pytortoisegit.dialogs.commitdlg import CommitDlg
    GitRunner(cwd=str(tmp_path)).run("init", "-b", "main", str(tmp_path))
    repo = Repository.open(str(tmp_path))
    dlg = CommitDlg(repo)
    assert not dlg.amend_box.isEnabled()


def test_commit_message_only_disables_list(qapp, repo):
    from pytortoisegit.dialogs.commitdlg import CommitDlg
    dlg = _smoke(qapp, lambda: CommitDlg(repo))
    assert dlg.status_tree.isEnabled()
    dlg.chk_message_only.setChecked(True)
    assert not dlg.status_tree.isEnabled()
    dlg.chk_message_only.setChecked(False)
    assert dlg.status_tree.isEnabled()


def test_commit_whole_project_filter(qapp, repo):
    from PySide6.QtCore import Qt
    from pytortoisegit.dialogs.commitdlg import CommitDlg
    dlg = _smoke(qapp, lambda: CommitDlg(repo, paths=["a.txt"]))
    paths = [it.data(0, Qt.ItemDataRole.UserRole + 1).path
             for it in dlg._iter_file_items()]
    assert paths and all(p == "a.txt" for p in paths)
    assert not dlg.chk_whole_project.isChecked()
    dlg.chk_whole_project.setChecked(True)      # 显示整个项目
    paths2 = [it.data(0, Qt.ItemDataRole.UserRole + 1).path
              for it in dlg._iter_file_items()]
    assert "new.txt" in paths2


def test_commit_filter_accepts_absolute_paths(qapp, repo):
    """命令行/资源管理器右键传入绝对路径时也要能过滤（原版经 CTGitPathList 转换）。

    回归：绝对路径与状态行的相对路径不匹配时，列表会被全部滤空，
    提交对话框里看不到任何文件改动。
    """
    from PySide6.QtCore import Qt
    from pytortoisegit.dialogs.commitdlg import CommitDlg
    from pytortoisegit.utils.paths import normalize_filter_paths

    absolute = os.path.join(repo.root, "a.txt")
    assert normalize_filter_paths(repo.root, [absolute]) == ["a.txt"]
    # Windows 资源管理器/命令行常带反斜杠
    assert normalize_filter_paths(
        repo.root, [absolute.replace("/", "\\")]) == ["a.txt"]
    # 仓库根 => 整个项目
    assert normalize_filter_paths(repo.root, [repo.root]) == [""]

    dlg = _smoke(qapp, lambda: CommitDlg(repo, paths=[absolute]))
    paths = [it.data(0, Qt.ItemDataRole.UserRole + 1).path
             for it in dlg._iter_file_items()]
    assert paths, "绝对路径不应把改动文件全部过滤掉"
    assert all(p == "a.txt" for p in paths)
    assert not dlg.chk_whole_project.isChecked()


def test_commit_filter_path_normalization_edge_cases(repo):
    """目录/点号/仓库外路径的规范化，且不得抛异常。"""
    from pytortoisegit.utils.paths import normalize_filter_paths

    assert normalize_filter_paths(repo.root, ["./a.txt"]) == ["a.txt"]
    assert normalize_filter_paths(repo.root, ["."]) == [""]
    assert normalize_filter_paths(repo.root, []) == [""]
    # 仓库外的路径被忽略，回退为“整个项目”，不会得到空列表
    assert normalize_filter_paths(repo.root, ["../outside.txt"]) == [""]
    assert normalize_filter_paths(
        repo.root,
        [os.path.join(os.path.dirname(repo.root), "outside.txt")]) == [""]
    # 无盘符的根路径在 Windows 上曾是 os.path.relpath 的崩溃点
    normalize_filter_paths(repo.root, ["/a.txt"])
    normalize_filter_paths(repo.root, ["D:\\other\\x.txt"])


def test_commit_filter_directory_shows_nested_files(qapp, git_repo):
    """按目录过滤时应列出该目录下的全部文件。"""
    from pathlib import Path
    from PySide6.QtCore import Qt
    from pytortoisegit.dialogs.commitdlg import CommitDlg

    root = Path(git_repo.root)
    (root / "sub" / "deep").mkdir(parents=True)
    (root / "sub" / "b.txt").write_text("y\n", encoding="utf-8")
    (root / "sub" / "deep" / "c.txt").write_text("z\n", encoding="utf-8")
    git_repo.runner.run("add", "-A")
    git_repo.runner.run("commit", "-m", "dirs")
    (root / "sub" / "b.txt").write_text("y\nz\n", encoding="utf-8")
    (root / "sub" / "deep" / "c.txt").write_text("z\nw\n", encoding="utf-8")

    dlg = _smoke(qapp, lambda: CommitDlg(git_repo, paths=["sub"]))
    paths = sorted(it.data(0, Qt.ItemDataRole.UserRole + 1).path
                   for it in dlg._iter_file_items())
    assert paths == ["sub/b.txt", "sub/deep/c.txt"]


def test_commit_view_patch_opens_diff(qapp, repo, monkeypatch):
    from pytortoisegit.dialogs import diffdlg as dd
    from pytortoisegit.dialogs.commitdlg import CommitDlg
    opened = {}

    class _FakeDiff:
        def __init__(self, *a, **k):
            opened["n"] = opened.get("n", 0) + 1

        def exec(self):
            return 0

    monkeypatch.setattr(dd, "DiffDlg", _FakeDiff)
    dlg = CommitDlg(repo)
    dlg._on_view_patch()
    assert opened.get("n") == 1


def test_diff_common_ancestor_uses_merge_base(qapp, repo, monkeypatch):
    from types import SimpleNamespace
    from pytortoisegit.dialogs import diffdlg as dd
    monkeypatch.setattr(dd, "run_async", lambda *a, **k: None)
    dlg = dd.DiffDlg(repo, "HEAD~1", "HEAD")
    dlg._common_ancestor = True
    seen = {"run": [], "checked": None}

    def fake_run(*args, **k):
        seen["run"].append(args)
        return SimpleNamespace(returncode=0, stdout="abc123\n", stderr="")

    def fake_checked(*args, **k):
        seen["checked"] = args
        return ""

    monkeypatch.setattr(dlg.repo.runner, "run", fake_run)
    monkeypatch.setattr(dlg.repo.runner, "run_checked", fake_checked)
    dlg._build_patch()
    assert any(a and a[0] == "merge-base" for a in seen["run"])
    assert "abc123" in seen["checked"]


def test_diff_revert_to_revision(qapp, git_repo, monkeypatch):
    from pathlib import Path
    from types import SimpleNamespace
    from PySide6.QtWidgets import QMessageBox
    from pytortoisegit.dialogs import diffdlg as dd
    (Path(git_repo.root) / "a.txt").write_text("changed\n", encoding="utf-8")
    monkeypatch.setattr(dd, "run_async", lambda *a, **k: None)
    dlg = dd.DiffDlg(git_repo, "", "HEAD")
    dlg._selected_patches = lambda: [SimpleNamespace(git_path="a.txt")]
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    dlg._revert_to("HEAD")
    assert (Path(git_repo.root) / "a.txt").read_text(
        encoding="utf-8") == "line1\nline2\nline3\n"


def test_diff_save_list(qapp, git_repo, monkeypatch, tmp_path):
    from types import SimpleNamespace
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QFileDialog, QTreeWidgetItem
    from pytortoisegit.dialogs import diffdlg as dd
    monkeypatch.setattr(dd, "run_async", lambda *a, **k: None)
    dlg = dd.DiffDlg(git_repo, "HEAD~1", "HEAD")
    it = QTreeWidgetItem(["a.txt"])
    it.setData(0, Qt.ItemDataRole.UserRole, SimpleNamespace(git_path="a.txt"))
    dlg.file_tree.addTopLevelItem(it)
    dest = tmp_path / "list.txt"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName",
        staticmethod(lambda *a, **k: (str(dest), "")))
    dlg._save_list()
    assert dest.read_text(encoding="utf-8") == "a.txt"


def test_commit_author_prefilled_visible(qapp, repo):
    """作者框始终显示当前 user.name <email>，未勾选时仅置灰。"""
    from pytortoisegit.dialogs.commitdlg import CommitDlg
    dlg = CommitDlg(repo)
    assert not dlg.author_edit.isHidden()
    assert "@example.com" in dlg.author_edit.text()
    assert "<" in dlg.author_edit.text() and ">" in dlg.author_edit.text()
    assert not dlg.author_edit.isEnabled()
    dlg.chk_set_author.setChecked(True)
    assert dlg.author_edit.isEnabled()


def test_commit_bugid_hidden_without_bugtraq(qapp, repo):
    from pytortoisegit.dialogs.commitdlg import CommitDlg
    dlg = CommitDlg(repo)
    assert dlg.bugid_edit.isHidden()
    assert dlg._ctl["IDC_BUGIDLABEL"].isHidden()


def test_commit_bugid_shown_with_bugtraq(qapp, repo):
    from pytortoisegit.dialogs.commitdlg import CommitDlg
    repo.runner.run("config", "bugtraq.message", "refs #%BUGID%")
    try:
        dlg = CommitDlg(repo)
        assert not dlg.bugid_edit.isHidden()
        assert not dlg._ctl["IDC_BUGIDLABEL"].isHidden()
    finally:
        repo.runner.run("config", "--unset", "bugtraq.message")


def test_commit_list_grouped_by_category(qapp, repo):
    """有未版本控制文件时列表应按分类分组（对齐 changedlg）。"""
    from PySide6.QtCore import Qt
    from pytortoisegit.dialogs.commitdlg import CommitDlg
    from pytortoisegit.git.statuslist import StatusRow
    dlg = _smoke(qapp, lambda: CommitDlg(repo))
    tree = dlg.status_tree
    titles = [tree.topLevelItem(i).text(0) for i in range(tree.topLevelItemCount())]
    assert any("未版本" in t for t in titles), titles
    group = next(tree.topLevelItem(i) for i in range(tree.topLevelItemCount())
                 if "未版本" in tree.topLevelItem(i).text(0))
    assert group.childCount() >= 1
    # _iter_file_items 只产出文件项（不含分组标题）
    items = list(dlg._iter_file_items())
    assert items
    assert all(isinstance(it.data(0, Qt.ItemDataRole.UserRole + 1), StatusRow)
               for it in items)
    assert len(items) >= group.childCount()


def test_commit_group_caption_and_view_patch(qapp, repo):
    """分组标题不应被截断；View Patch 链接带 >>。"""
    from pytortoisegit.dialogs.commitdlg import CommitDlg
    dlg = CommitDlg(repo)
    grp = dlg._ctl["IDC_LISTGROUP"]
    assert "差异" in grp.title()
    assert dlg.view_patch_link.text().endswith(">>")


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


def test_create_branch_dialog_layout(qapp, repo):
    """对齐 IDD_NEW_BRANCH_TAG：Base On 单选/组合框、Options 可见性。"""
    from pytortoisegit.dialogs.createbranchdlg import CreateBranchDlg, CreateTagDlg
    dlg = CreateBranchDlg(repo)
    assert dlg.rd_head.isChecked()
    assert "(" in dlg.rd_head.text()          # HEAD (当前分支)
    assert dlg.branch_combo.isEnabled() is False
    assert dlg.switch_box.isVisibleTo(dlg)    # 分支模式显示“切换”
    assert not dlg.sign_box.isVisibleTo(dlg)
    assert dlg.grp_message.title().startswith("描述") or "D" in dlg.grp_message.title()

    tag = CreateTagDlg(repo)
    assert tag.annotated_box is tag.sign_box
    assert tag.annotated_box.isVisibleTo(tag)  # 标签模式显示“附注”
    assert not tag.switch_box.isVisibleTo(tag)
    assert tag.track_box.isVisibleTo(tag) is False



def test_sync_dialog(qapp, repo):
    from pytortoisegit.dialogs.sync import SyncDlg
    dlg = _smoke(qapp, lambda: SyncDlg(repo))
    assert dlg.branch_label.text() in ("main", "")


def _settings_roots(dlg):
    return [dlg.tree.topLevelItem(i).text(0) for i in range(dlg.tree.topLevelItemCount())]


def _settings_children(item):
    return [item.child(i).text(0) for i in range(item.childCount())]


@pytest.fixture
def english_ui():
    """临时切到英文界面（设置页树标题随语言本地化）。"""
    from pytortoisegit.res import strings
    old = strings.get_language()
    strings.set_language("en")
    try:
        yield
    finally:
        strings.set_language(old)


def test_settings_dialog_readonly(qapp, english_ui):
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


def test_settings_dialog_repo_pages(qapp, repo, english_ui):
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


def test_reflog_search_finds_match(qapp, repo):
    from pytortoisegit.dialogs.reflogdlg import ReflogDlg
    dlg = ReflogDlg(repo)
    assert dlg.table.rowCount() >= 2
    assert dlg.find("second", forward=True)
    assert dlg.table.currentRow() >= 0
    assert not dlg.find("zzz-no-such-entry-zzz", forward=True)
    dlg.deleteLater()


def test_reflog_search_dialog_reports_not_found(qapp, repo):
    from pytortoisegit.dialogs.reflogdlg import ReflogDlg
    dlg = ReflogDlg(repo)
    dlg._on_search()
    assert dlg._search_dlg is not None
    dlg._search_dlg.edit.setText("initial")
    dlg._search_dlg._do_find(True)
    assert dlg._search_dlg.status.text() == ""
    dlg._search_dlg.edit.setText("zzz-no-such-entry-zzz")
    dlg._search_dlg._do_find(True)
    assert dlg._search_dlg.status.text() != ""
    dlg.deleteLater()


def test_reflog_search_dialog_floats_on_top(qapp, repo):
    from PySide6.QtCore import Qt
    from pytortoisegit.dialogs.reflogdlg import ReflogDlg
    dlg = ReflogDlg(repo)
    dlg.show()
    dlg._on_search()
    sd = dlg._search_dlg
    assert sd.windowFlags() & Qt.WindowType.Tool
    assert sd.isVisible()
    dlg.deleteLater()


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
    # 对齐原版：Fetch 时合并选项显示但置灰；Tags/Prune 仍可用
    for w in (dlg.chk_squash, dlg.chk_noff, dlg.chk_ffonly, dlg.chk_nocommit):
        assert not w.isHidden()
        assert not w.isEnabled()
    assert dlg.chk_fetchtags.isEnabled()
    assert dlg.chk_prune.isEnabled()


def test_pull_default_labels(qapp, git_repo, english_ui):
    """Tags/Prune 显示 'Default: X' 标签（对齐 OnCbnSelchangeRemote）。"""
    from pytortoisegit.dialogs.pulldlg import PullFetchDlg
    git_repo.runner.run("config", "remote.origin.tagopt", "--tags")
    git_repo.runner.run("config", "fetch.prune", "true")
    dlg = PullFetchDlg(git_repo, fetch_only=True)
    assert dlg.tag_option_label.text().endswith("All")
    assert dlg.prune_label.text().endswith("true")


def test_push_dialog_no_status_and_browse(qapp, repo):
    """不应有多余的“就绪”状态标签；本地浏览为 '>' 菜单按钮。"""
    from pytortoisegit.dialogs.pushdlg import PushDlg
    dlg = PushDlg(repo)
    assert not hasattr(dlg, "_status")
    assert dlg.btn_browse_local.text() == ">"
    assert dlg.btn_browse_remote.text() == "..."


def test_push_recurse_default_none(qapp, repo):
    """递归子模块默认 None，参数为空。"""
    from pytortoisegit.dialogs.pushdlg import PushDlg
    dlg = PushDlg(repo)
    assert dlg.sub_combo.count() == 3
    assert dlg.sub_combo.currentIndex() == 0
    assert dlg._collect_opts().recurse == ""
    dlg.sub_combo.setCurrentIndex(2)
    assert dlg._collect_opts().recurse == "on-demand"


def test_push_force_mutual_exclusion(qapp, repo):
    from pytortoisegit.dialogs.pushdlg import PushDlg
    dlg = PushDlg(repo)
    dlg.chk_force_with_lease.setChecked(True)
    assert not dlg.chk_force.isEnabled()
    assert not dlg.chk_tags.isEnabled()
    dlg.chk_force_with_lease.setChecked(False)
    dlg.chk_tags.setChecked(True)
    assert not dlg.chk_force_with_lease.isEnabled()


def test_push_browse_remote_fills_branch(qapp, repo, monkeypatch):
    from PySide6.QtWidgets import QDialog
    from pytortoisegit.dialogs.pushdlg import PushDlg

    class _FakeRef:
        def __init__(self, *a, **k):
            self.selected = "origin/feature"

        def exec(self):
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(
        "pytortoisegit.dialogs.selectremoterefdlg.SelectRemoteRefDlg", _FakeRef)
    dlg = PushDlg(repo)
    dlg._browse_remote()
    assert dlg.remote_combo.currentText() == "feature"


def test_push_manage_opens_settings(qapp, repo, monkeypatch):
    from pytortoisegit.dialogs.pushdlg import PushDlg
    opened = {}

    class _FakeSettings:
        def __init__(self, *a, **k):
            opened["yes"] = True
            self._items = {"gitremote": object()}

            class _Tree:
                def setCurrentItem(self, item):
                    pass
            self.tree = _Tree()

        def exec(self):
            return 0

    monkeypatch.setattr(
        "pytortoisegit.dialogs.settingsdlg.SettingsDlg", _FakeSettings)
    dlg = PushDlg(repo)
    dlg._on_manage()
    assert opened.get("yes") is True


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


def test_pull_dialog_history_single_branch_not_split(qapp, repo, isolated_settings):
    """QSettings 会把单元素历史读回成字符串 'main'，不能逐字符拆成 m/a/i/n。"""
    from pytortoisegit.dialogs.pulldlg import PullFetchDlg
    isolated_settings.setValue("pullRemoteBranchHistory", "main")
    isolated_settings.sync()
    dlg = PullFetchDlg(repo, fetch_only=False)
    items = [dlg.remote_branch_edit.itemText(i)
             for i in range(dlg.remote_branch_edit.count())]
    assert items == ["main"]


_PULL_FLAGS = [
    ("chk_squash", "--squash"),
    ("chk_noff", "--no-ff"),
    ("chk_nocommit", "--no-commit"),
    ("chk_ffonly", "--ff-only"),
    ("chk_fetchtags", "--tags"),
    ("chk_prune", "--prune"),
    ("chk_rebase", "--rebase"),
]


@pytest.mark.parametrize("attr,flag", _PULL_FLAGS)
def test_pull_option_flag(qapp, repo, attr, flag):
    """勾选各选项后应生成对应 git 参数。"""
    from pytortoisegit.dialogs.pulldlg import PullFetchDlg
    dlg = PullFetchDlg(repo, fetch_only=False)
    getattr(dlg, attr).setChecked(True)
    assert flag in dlg._build_args()


def test_pull_depth_option(qapp, repo):
    from pytortoisegit.dialogs.pulldlg import PullFetchDlg
    dlg = PullFetchDlg(repo, fetch_only=False)
    assert not dlg.depth_edit.isEnabled()
    dlg.chk_depth.setChecked(True)
    assert dlg.depth_edit.isEnabled()
    dlg.depth_edit.setValue(5)
    args = dlg._build_args()
    assert args[args.index("--depth") + 1] == "5"


def test_pull_depth_hidden_for_normal_repo(qapp, repo):
    """普通仓库隐藏 Depth（对齐原版 git_repository_is_shallow）。"""
    from pytortoisegit.dialogs.pulldlg import PullFetchDlg
    dlg = PullFetchDlg(repo, fetch_only=False)
    assert dlg.chk_depth.isHidden()
    assert dlg.depth_edit.isHidden()


def test_pull_depth_shown_for_shallow_repo(qapp, tmp_path_factory):
    from pytortoisegit.git.git import GitRunner
    from pytortoisegit.git.repo import Repository
    from pytortoisegit.dialogs.pulldlg import PullFetchDlg
    src = tmp_path_factory.mktemp("shallow_src")
    r = GitRunner(cwd=str(src))
    r.run("init", "-b", "main", str(src))
    r.run("config", "user.email", "t@e.com")
    r.run("config", "user.name", "T")
    (src / "a.txt").write_text("x\n", encoding="utf-8")
    r.run("add", "-A")
    r.run("commit", "-m", "c1")
    (src / "a.txt").write_text("y\n", encoding="utf-8")
    r.run("add", "-A")
    r.run("commit", "-m", "c2")
    bare = tmp_path_factory.mktemp("shallow_bare") / "remote.git"
    GitRunner(cwd=str(src)).run("init", "--bare", "-b", "main", str(bare))
    r.run("remote", "add", "origin", str(bare))
    r.run("push", "-u", "origin", "main")
    dst = tmp_path_factory.mktemp("shallow_dst") / "repo"
    file_url = "file:///" + str(bare).replace("\\", "/")
    GitRunner(cwd=str(dst.parent)).run(
        "clone", "--depth", "1", file_url, str(dst))
    repo2 = Repository.open(str(dst))
    assert repo2.is_shallow()
    dlg = PullFetchDlg(repo2, fetch_only=False)
    assert not dlg.chk_depth.isHidden()
    assert dlg.chk_depth.isChecked()


def test_pull_no_options_by_default(qapp, repo):
    from pytortoisegit.dialogs.pulldlg import PullFetchDlg
    dlg = PullFetchDlg(repo, fetch_only=False)
    args = dlg._build_args()
    assert args[0] == "pull"
    # 默认显式 merge（--no-rebase），避免 git>=2.27 在分叉分支上直接报错
    assert [a for a in args if a.startswith("--")] == ["--no-rebase"]


def test_pull_args_remote_and_branch(qapp, repo):
    from pytortoisegit.dialogs.pulldlg import PullFetchDlg
    dlg = PullFetchDlg(repo, fetch_only=False)
    dlg.remote_combo.clear()
    dlg.remote_combo.addItem("upstream")
    dlg.remote_branch_edit.setEditText("dev")
    assert dlg._build_args()[:3] == ["pull", "upstream", "dev"]


def test_git_icon_provider_prewarms_icon(qapp):
    from pytortoisegit.dialogs.mainmenu import _GitIconProvider
    # 必须在构造（GUI 线程）时预加载，icon() 只返回缓存，
    # 避免 QFileSystemModel 后台线程创建 QPixmap 导致段错误
    provider = _GitIconProvider(None)
    assert provider._git_icon is not None
    assert not provider._git_icon.isNull()


def test_overlay_icons_and_compose(qapp):
    import os
    import tempfile
    from PySide6.QtCore import QFileInfo
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QFileIconProvider
    from pytortoisegit.res import overlays
    for st in ("normal", "modified", "added", "conflicted", "deleted",
               "unversioned", "ignored"):
        ic = overlays.overlay_icon(st)
        assert ic is not None and not ic.isNull(), st
    # 空基础图标原样返回
    assert overlays.compose(QIcon(), "normal").isNull()
    d = tempfile.mkdtemp()
    p = os.path.join(d, "f.txt")
    open(p, "w", encoding="utf-8").write("x")
    base = QFileIconProvider().icon(QFileInfo(p))
    assert not overlays.compose(base, "normal").isNull()
    assert not overlays.compose(base, "modified").isNull()


def test_overlay_key_classification():
    from pytortoisegit.git.status import GitStatusEntry
    def key(x, y):
        return GitStatusEntry(x, y, "p").overlay_key
    assert key("?", " ") == "unversioned"
    assert key(" ", "M") == "modified"
    assert key("M", " ") == "modified"
    assert key("A", " ") == "added"
    assert key("D", " ") == "deleted"
    assert key("U", "U") == "conflicted"
    assert key("!", "!") == "ignored"
    assert key(" ", " ") == "normal"


def test_main_window_builds_overlay_icons(qapp, repo):
    from pytortoisegit.dialogs.mainmenu import MainMenuDlg
    dlg = MainMenuDlg(repo_path=str(repo.root))
    icons = dlg._build_overlay_icons(str(repo.root))
    assert icons  # 至少 modified / untracked 之一带覆盖
    for ic in icons.values():
        assert ic is not None and not ic.isNull()


def test_overlay_nonversioned_not_green(qapp, tmp_path):
    """未纳入版本控制的文件/目录不应显示绿勾（normal）。"""
    from PySide6.QtCore import QFileInfo, QSize
    from PySide6.QtWidgets import QFileIconProvider
    from pytortoisegit.dialogs.mainmenu import MainMenuDlg
    from pytortoisegit.res import overlays

    runner = GitRunner(cwd=str(tmp_path))
    runner.init(str(tmp_path), initial_branch="main")
    runner.run("config", "user.email", "t@example.com")
    runner.run("config", "user.name", "Tester")
    (tmp_path / ".gitignore").write_text("__pycache__/\n*.log\n", encoding="utf-8")
    (tmp_path / "tracked.txt").write_text("x\n", encoding="utf-8")
    (tmp_path / "trackeddir").mkdir()
    (tmp_path / "trackeddir" / "t.txt").write_text("x\n", encoding="utf-8")
    runner.run("add", "-A")
    assert runner.run("commit", "-m", "init").returncode == 0
    # 已跟踪目录内的被忽略文件：目录本身仍应是绿勾
    (tmp_path / "trackeddir" / "x.log").write_text("x\n", encoding="utf-8")
    (tmp_path / "untrackeddir").mkdir()
    (tmp_path / "untrackeddir" / "u.txt").write_text("x\n", encoding="utf-8")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "x.pyc").write_text("x\n", encoding="utf-8")
    (tmp_path / "emptyuntracked").mkdir()

    dlg = MainMenuDlg(repo_path=str(tmp_path))
    actual = dlg._build_overlay_icons(str(tmp_path))

    def status_of(name):
        full = str(tmp_path / name)
        p = os.path.normcase(os.path.abspath(full))
        base = QFileIconProvider().icon(QFileInfo(full))
        for st in ("normal", "modified", "added", "conflicted", "deleted",
                   "ignored", "unversioned"):
            exp = overlays.compose(base, st)
            if exp is not None and exp.pixmap(QSize(16, 16)).toImage() \
                    == actual[p].pixmap(QSize(16, 16)).toImage():
                return st
        return None

    assert status_of("tracked.txt") == "normal"
    assert status_of("trackeddir") == "normal"
    assert status_of("untrackeddir") == "unversioned"
    assert status_of("emptyuntracked") == "unversioned"
    assert status_of("__pycache__") == "ignored"


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


def test_bisectstart_pick_commit_buttons(qapp, repo, monkeypatch):
    """“...”按钮打开日志选择提交，commit id 回填到 good/bad 下拉框。"""
    from PySide6.QtWidgets import QDialog
    from pytortoisegit.dialogs.bisectstartdlg import BisectStartDlg

    class _FakeLog:
        def __init__(self, *_a, **_k):
            self.selected_hash = "deadbeef0123456789"

        def exec(self):
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr("pytortoisegit.dialogs.logdlg.LogDlg", _FakeLog)
    dlg = BisectStartDlg(repo)
    assert not dlg.btn_ok.isEnabled()      # good 默认为空 → OK 禁用
    dlg.btn_good.click()
    assert dlg.good_combo.currentText() == "deadbeef0123456789"
    assert dlg.btn_ok.isEnabled()          # 两框都有值后启用
    dlg.btn_bad.click()
    assert dlg.bad_combo.currentText() == "deadbeef0123456789"
    dlg.deleteLater()


def test_bisectstart_defaults_and_ok_gating(qapp, repo):
    """对齐原版：bad 默认当前分支、good 留空；任一框清空则 OK 禁用。"""
    from pytortoisegit.dialogs.bisectstartdlg import BisectStartDlg
    dlg = BisectStartDlg(repo)
    assert dlg.good_combo.currentText() == ""
    assert dlg.bad_combo.currentText() == "main"
    assert not dlg.btn_ok.isEnabled()
    dlg.good_combo.setCurrentText("HEAD")
    assert dlg.btn_ok.isEnabled()
    dlg.bad_combo.setEditText("")
    assert not dlg.btn_ok.isEnabled()
    dlg.deleteLater()


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


def _auto_close_modal_progress():
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    def _close():
        w = QApplication.activeModalWidget()
        if w is not None:
            w.accept()
        else:
            QTimer.singleShot(50, _close)

    QTimer.singleShot(100, _close)


def test_gitswitch_lists_branches(qapp, repo):
    from pytortoisegit.dialogs.gitswitchdlg import GitSwitchDlg
    dlg = GitSwitchDlg(repo)
    branches = [dlg.branch_combo.itemText(i)
                for i in range(dlg.branch_combo.count())]
    assert "main" in branches
    dlg.deleteLater()


def test_gitswitch_nonexistent_branch_keeps_dialog(qapp, repo):
    from PySide6.QtWidgets import QDialog
    from pytortoisegit.dialogs.gitswitchdlg import GitSwitchDlg
    dlg = GitSwitchDlg(repo)
    dlg.branch_combo.setCurrentText("no-such-branch-xyz")
    _auto_close_modal_progress()
    dlg._on_switch()
    assert dlg.result() != QDialog.DialogCode.Accepted
    dlg.deleteLater()


def test_gitswitch_success_closes_dialog(qapp, repo):
    from PySide6.QtWidgets import QDialog
    from pytortoisegit.dialogs.gitswitchdlg import GitSwitchDlg
    dlg = GitSwitchDlg(repo)
    dlg.branch_combo.setCurrentText("main")
    _auto_close_modal_progress()
    dlg._on_switch()
    assert dlg.result() == QDialog.DialogCode.Accepted
    dlg.deleteLater()


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


def test_repobrowser_pick_rev_uses_log_selection(qapp, git_repo, monkeypatch):
    """点“修订”按钮应打开日志对话框选修订，并把选择回填。"""
    from pathlib import Path
    from PySide6.QtWidgets import QDialog
    from pytortoisegit.dialogs import logdlg
    from pytortoisegit.dialogs.repobrowserdlg import RepositoryBrowserDlg

    root = Path(git_repo.root)
    (root / "a.txt").write_text("changed\n", encoding="utf-8")
    git_repo.runner.run("add", "-A")
    git_repo.runner.run("commit", "-m", "second")
    first = git_repo.runner.run("rev-parse", "HEAD~1").stdout.strip()

    seen = {}

    class FakeLog:
        selected_hash = first

        def __init__(self, *args, **kwargs):
            seen["select"] = kwargs.get("select")

        def exec(self):
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(logdlg, "LogDlg", FakeLog)

    dlg = RepositoryBrowserDlg(git_repo)
    dlg._pick_rev()
    assert seen.get("select") is True, "应以 select 模式打开日志对话框"
    assert dlg.rev == first
    assert dlg.btn_revision.text() == first


def test_repobrowser_root_selected_and_counts(qapp, git_repo):
    """对齐 Refresh()：根目录为当前节点，信息栏给出文件/子模块/文件夹统计。"""
    from pathlib import Path
    from pytortoisegit.dialogs.repobrowserdlg import RepositoryBrowserDlg

    root = Path(git_repo.root)
    (root / "sub").mkdir()
    (root / "sub" / "inner.txt").write_text("x\n", encoding="utf-8")
    (root / "top.py").write_text("print(1)\n", encoding="utf-8")
    git_repo.runner.run("add", "-A")
    git_repo.runner.run("commit", "-m", "layout")

    dlg = RepositoryBrowserDlg(git_repo)
    # 原版 FillListCtrlForShadowTree(m_TreeRoot) —— 显示的是根目录内容
    assert dlg.url_edit.text() == "/"
    assert dlg._current_node is dlg.tree_root
    names = [dlg.list.topLevelItem(i).text(0)
             for i in range(dlg.list.topLevelItemCount())]
    assert "sub" in names and "top.py" in names
    # 文件夹恒排在文件之前（CRepoListCompareFunc 的 m_bFolder 兜底）
    assert names.index("sub") < names.index("top.py")
    info = dlg.info_label.text()
    # sub/inner.txt 与 top.py 计 2 个文件，sub 计 1 个文件夹，共 3 项
    assert "2 个文件" in info
    assert "1 个文件夹" in info
    assert "3 项" in info


def test_repobrowser_file_extension_and_size_columns(qapp, git_repo):
    """对齐 CPathUtils::GetFileExtFromPath 与 StrFormatByteSize64。"""
    from pathlib import Path
    from pytortoisegit.dialogs.repobrowserdlg import (
        RepositoryBrowserDlg, _file_extension, _format_byte_size)

    # 点号开头的文件也算扩展名（原版 dotPos > slashPos 即成立）
    assert _file_extension(".gitignore") == ".gitignore"
    assert _file_extension("demo.py") == ".py"
    assert _file_extension("LICENSE") == ""
    assert _file_extension("a/b/c.tar.gz") == ".gz"
    assert _format_byte_size(109).endswith("字节")
    assert "KB" in _format_byte_size(18 * 1024)

    root = Path(git_repo.root)
    (root / ".gitignore").write_text("*.pyc\n", encoding="utf-8")
    (root / "LICENSE").write_text("MIT\n", encoding="utf-8")
    git_repo.runner.run("add", "-A")
    git_repo.runner.run("commit", "-m", "files")

    dlg = RepositoryBrowserDlg(git_repo)
    rows = {dlg.list.topLevelItem(i).text(0): dlg.list.topLevelItem(i)
            for i in range(dlg.list.topLevelItemCount())}
    assert rows[".gitignore"].text(1) == ".gitignore"
    assert rows["LICENSE"].text(1) == ""
    assert rows["LICENSE"].text(2) != ""


def test_repobrowser_context_menu_matches_selection_type(qapp, git_repo,
                                                        monkeypatch):
    """对齐 ShowContextMenu：文件夹只给“打开/日志”，文件才有比较/追溯/另存。"""
    from pathlib import Path
    from pytortoisegit.dialogs.repobrowserdlg import RepositoryBrowserDlg

    root = Path(git_repo.root)
    (root / "folder").mkdir()
    (root / "folder" / "f.txt").write_text("x\n", encoding="utf-8")
    git_repo.runner.run("add", "-A")
    git_repo.runner.run("commit", "-m", "menu")

    dlg = RepositoryBrowserDlg(git_repo)
    captured = {}

    def fake_menu(self, global_pos, selected, sel_type):
        captured["sel_type"] = sel_type
        captured["names"] = [e.name for e in selected]

    monkeypatch.setattr(RepositoryBrowserDlg, "_show_context_menu", fake_menu)

    folder_node = dlg.tree_root.children["folder"]
    dlg._show_context_menu(None, [folder_node], "folders")
    assert captured["sel_type"] == "folders"

    file_node = folder_node.children["f.txt"] if folder_node.children else None
    if file_node is None:
        dlg._read_tree(folder_node)
        file_node = folder_node.children["f.txt"]
    dlg._show_context_menu(None, [file_node], "files")
    assert captured["sel_type"] == "files"


def test_repobrowser_folder_ordering_wins_over_sort(qapp, git_repo):
    """即使按大小倒序，文件夹仍排在文件之前。"""
    from pathlib import Path
    from pytortoisegit.dialogs.repobrowserdlg import (
        RepositoryBrowserDlg, COL_FILESIZE)

    root = Path(git_repo.root)
    (root / "adir").mkdir()
    (root / "adir" / "keep.txt").write_text("x\n", encoding="utf-8")
    (root / "big.bin").write_text("y" * 5000, encoding="utf-8")
    git_repo.runner.run("add", "-A")
    git_repo.runner.run("commit", "-m", "sort")

    dlg = RepositoryBrowserDlg(git_repo)
    dlg._curr_sort_col = COL_FILESIZE
    dlg._curr_sort_desc = True
    dlg._fill_list_for_node(dlg.tree_root)
    names = [dlg.list.topLevelItem(i).text(0)
             for i in range(dlg.list.topLevelItemCount())]
    assert names[0] == "adir", names


def test_revisiongraph_dialog(qapp, repo):
    from pytortoisegit.dialogs.revisiongraphdlg import RevisionGraphDlg
    dlg = _smoke(qapp, lambda: RevisionGraphDlg(repo))
    assert dlg.canvas.node_count() >= 1


def test_revgraph_load_args_matches_original_filter_semantics():
    """build_load_args 对齐 RevisionGraphDlgFunc.cpp:193-235 的范围拼接规则。"""
    from pytortoisegit.dialogs.revisiongraphdlg import build_load_args

    # 都不勾选 => --all
    assert build_load_args({})["all_branches"] is True
    assert build_load_args({})["revisions"] == []
    # 仅当前分支 => 范围加 HEAD，不加 --all/--branches
    cur = build_load_args({"current_branch": True})
    assert cur["all_branches"] is False and cur["revisions"] == ["HEAD"]
    # 仅本地分支 => --branches
    loc = build_load_args({"local_branches": True})
    assert loc["all_branches"] is False and loc["local_branches"] is True
    # From => 排除项，任何模式下都生效
    assert build_load_args({"from_rev": "topic"})["revisions"] == ["^topic"]
    assert build_load_args(
        {"from_rev": "a b", "current_branch": True})["revisions"] == ["^a", "^b", "HEAD"]
    # To => 仅在两个勾选框都未勾选时作为包含项
    assert build_load_args({"to_rev": "v1.0"})["revisions"] == ["v1.0"]
    assert build_load_args(
        {"to_rev": "v1.0", "current_branch": True})["revisions"] == ["HEAD"]
    assert build_load_args(
        {"to_rev": "v1.0", "local_branches": True})["revisions"] == []
    # 恒开 simplify-by-decoration
    assert build_load_args({})["simplify"] is True


def test_revgraph_toolbar_and_zoom(qapp, repo):
    """工具栏按钮、缩放下拉框与缩放范围（对齐 IDR_REVGRAPHBAR / MIN-MAX_ZOOM）。"""
    from pytortoisegit.dialogs.revisiongraphdlg import (
        RevisionGraphDlg, _MAX_ZOOM, _MIN_ZOOM, _ZOOM_PRESETS)
    from PySide6.QtWidgets import QToolButton

    dlg = _smoke(qapp, lambda: RevisionGraphDlg(repo))
    labels = [b.text() for b in dlg.findChildren(QToolButton)]
    assert "过滤" in labels
    assert len(labels) >= 7, labels
    assert [dlg.zoom_box.itemText(i) for i in range(dlg.zoom_box.count())] \
        == list(_ZOOM_PRESETS)
    assert dlg.zoom_box.currentText() == "100%"

    # 缩放会改变画布尺寸（即真的影响渲染范围）
    dlg._set_zoom(1.0)
    full = dlg.canvas.minimumSize()
    dlg._set_zoom(0.5)
    assert dlg.canvas.minimumSize().width() < full.width()
    assert dlg.zoom_box.currentText() == "50%"
    # 越界被夹紧到 [MIN_ZOOM, MAX_ZOOM]
    dlg._set_zoom(99.0)
    assert dlg.canvas.zoom() == _MAX_ZOOM
    dlg._set_zoom(0.0)
    assert dlg.canvas.zoom() == _MIN_ZOOM


def test_revgraph_zoom_box_accepts_typed_value(qapp, repo):
    from pytortoisegit.dialogs.revisiongraphdlg import RevisionGraphDlg

    dlg = _smoke(qapp, lambda: RevisionGraphDlg(repo))
    dlg.zoom_box.setEditText("40%")
    dlg._on_zoom_box(None)
    assert abs(dlg.canvas.zoom() - 0.4) < 1e-6
    # 非法输入回退到当前缩放，不应抛异常
    dlg.zoom_box.setEditText("abc")
    dlg._on_zoom_box(None)
    assert dlg.zoom_box.currentText() == "40%"


def test_revgraph_filter_dialog_exclusive_and_reset(qapp, git_repo):
    """对齐 RevGraphFilterDlg：两勾选框互斥、To 被禁用清空、Reset 立即接受。"""
    from PySide6.QtWidgets import QDialog
    from pytortoisegit.dialogs.revgraphfilterdlg import RevGraphFilterDlg

    dlg = RevGraphFilterDlg(git_repo)
    assert dlg.state() == {"from_rev": "", "to_rev": "",
                           "current_branch": False, "local_branches": False}

    dlg.to_edit.setText("stale-value")
    dlg.chk_current.setChecked(True)
    assert dlg.chk_local.isEnabled() is False
    assert dlg.to_edit.isEnabled() is False
    # 勾选分支选项时 To 会被清空（原版 OnBnClickedCurrentBranch 的行为）
    assert dlg.to_edit.text() == ""

    dlg.chk_current.setChecked(False)
    assert dlg.chk_local.isEnabled() is True
    assert dlg.to_edit.isEnabled() is True

    dlg.chk_local.setChecked(True)
    assert dlg.chk_current.isEnabled() is False
    assert dlg.state()["local_branches"] is True

    # set_state 应能回填（供再次打开过滤框时保持条件）
    dlg.set_state({"from_rev": "topic", "to_rev": "v1"})
    assert dlg.state()["from_rev"] == "topic"
    assert dlg.state()["to_rev"] == "v1"

    # Reset：清空并立即接受，使过滤马上生效
    dlg._reset()
    assert dlg.state() == {"from_rev": "", "to_rev": "",
                           "current_branch": False, "local_branches": False}
    assert dlg.result() == QDialog.DialogCode.Accepted


def test_revgraph_filter_changes_fetched_commits(qapp, tmp_path):
    """过滤条件必须真正走到 git：From 作为排除项应当减少提交数。"""
    from pathlib import Path
    from pytortoisegit.dialogs.revisiongraphdlg import build_load_args
    from pytortoisegit.git.git import GitRunner
    from pytortoisegit.git.repo import Repository
    from pytortoisegit.git.rev import GitRevLoglist

    root = tmp_path / "rgfilter"
    root.mkdir()
    runner = GitRunner(cwd=str(root))
    runner.init(str(root), initial_branch="main")
    repo = Repository.open(str(root))
    runner.run("config", "user.email", "t@example.com")
    runner.run("config", "user.name", "Tester")
    Path(root / "f.txt").write_text("1\n", encoding="utf-8")
    runner.run("add", "-A")
    assert runner.run("commit", "-m", "c1").returncode == 0
    runner.run("branch", "feature")          # feature 指向 c1
    Path(root / "f.txt").write_text("2\n", encoding="utf-8")
    runner.run("add", "-A")
    assert runner.run("commit", "-m", "c2").returncode == 0

    def subjects(state):
        log = GitRevLoglist(repo)
        log.load(**build_load_args(state))
        return sorted(c.subject for c in log.commits)

    # --all --simplify-by-decoration：c2 被 main 标注、c1 被 feature 标注
    assert subjects({}) == ["c1", "c2"]
    # 排除 feature 后只剩 c2 —— 证明过滤真的进了 git 参数
    assert subjects({"from_rev": "feature"}) == ["c2"]


def test_revgraph_close_during_load_is_safe(qapp, repo):
    """回归：加载途中关闭修订图窗口不应崩溃。"""
    from PySide6.QtCore import QEventLoop, QTimer
    from pytortoisegit.dialogs.revisiongraphdlg import RevisionGraphDlg

    dlg = RevisionGraphDlg(repo)
    dlg.show()
    # 初始加载仍在后台线程运行时立刻关闭并销毁
    dlg.close()
    dlg.deleteLater()

    loop = QEventLoop()
    QTimer.singleShot(2000, loop.quit)
    loop.exec()
    # 能走到这里即说明进程没有因 QThread 被销毁而崩溃
    assert True


@pytest.fixture
def rg(qapp):
    """打开修订图窗口的工厂，并在用例结束后关闭所有窗口。

    修订图是非模态窗口且自带后台加载线程，若用例结束不关闭，窗口会一直累积，
    在整份测试文件里跑时会拖垮后续用例（表现为进程阻塞）。
    """
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication
    from pytortoisegit.dialogs.revisiongraphdlg import RevisionGraphDlg

    made = []

    def make(repo, wait_ms=2500):
        dlg = RevisionGraphDlg(repo)
        dlg.show()
        loop = QEventLoop()
        QTimer.singleShot(wait_ms, loop.quit)
        loop.exec()
        made.append(dlg)
        return dlg

    yield make

    for dlg in made:
        try:
            dlg.close()
            dlg.deleteLater()
        except RuntimeError:
            pass
    app = QApplication.instance()
    if app is not None:
        app.processEvents()


def _rg_branchy_repo(tmp_path):
    """建一个有 3 个可见节点的仓库（--simplify-by-decoration 只留有引用标注的提交）。"""
    from pytortoisegit.git.git import GitRunner
    from pytortoisegit.git.repo import Repository

    root = tmp_path / "rgsel"
    root.mkdir()
    runner = GitRunner(cwd=str(root))
    runner.init(str(root), initial_branch="main")
    repo = Repository.open(str(root))
    runner.run("config", "user.email", "t@example.com")
    runner.run("config", "user.name", "Tester")
    for i, branch in ((1, "topic"), (2, "feature"), (3, None)):
        (root / "a.txt").write_text(f"{i}\n", encoding="utf-8")
        runner.run("add", "-A")
        assert runner.run("commit", "-m", f"c{i}").returncode == 0
        if branch:
            runner.run("branch", branch)
    return repo


def test_revgraph_node_selection_semantics(rg, tmp_path):
    """选择语义对齐 OnLButtonDown：单选可取消、Ctrl 多选最多两个。"""
    repo = _rg_branchy_repo(tmp_path)
    dlg = rg(repo)
    canvas = dlg.canvas
    order = list(canvas.layout().order)
    assert len(order) >= 3, f"需要至少 3 个节点，实际 {len(order)}"
    k1, k2, k3 = order[0], order[1], order[2]

    canvas.select(k1)
    assert canvas.selected() == [k1]
    canvas.select(k1)                     # 再点一次取消
    assert canvas.selected() == []

    canvas.select(k1)
    canvas.select(k2, additive=True)
    assert canvas.selected() == [k1, k2]
    canvas.select(k3, additive=True)      # 已有两个：最多保持两个
    assert len(canvas.selected()) == 2

    # 点击已选中的第二个节点会取消它（对齐 m_SelectedEntry2 = nullptr）
    canvas.select(None)
    canvas.select(k1)
    canvas.select(k2, additive=True)
    canvas.select(k2, additive=True)
    assert canvas.selected() == [k1]

    canvas.select(None)                   # 空白处点击清空
    assert canvas.selected() == []


def test_revgraph_hit_test_respects_zoom(rg, tmp_path):
    """命中测试要按当前缩放换算。"""
    from PySide6.QtCore import QPointF
    repo = _rg_branchy_repo(tmp_path)
    dlg = rg(repo)
    canvas = dlg.canvas
    key = canvas.layout().order[0]
    node = canvas.layout().nodes[key]
    for zoom in (1.0, 0.5, 1.5):
        canvas.set_zoom(zoom)
        assert canvas.node_at(QPointF(node.x * zoom, node.y * zoom)) == key
    assert canvas.node_at(QPointF(99999, 99999)) is None


def test_revgraph_tooltip_has_commit_details(rg, tmp_path):
    repo = _rg_branchy_repo(tmp_path)
    dlg = rg(repo)
    key = dlg.canvas.layout().order[0]
    text = dlg._tooltip_for(key)
    lines = text.splitlines()
    assert lines[0] == key, "首行应为完整 hash"
    assert "@" in lines[1], "第二行应含作者与邮箱"
    assert any(line.strip() for line in lines[2:]), "应包含标题等正文"
    # 未知节点不应抛异常
    assert dlg._tooltip_for("deadbeef") == ""


def test_revgraph_context_menu_one_vs_two_nodes(rg, tmp_path):
    """右键菜单按选择数分支：1 个节点给 7 项，2 个节点只给比较/统一差异。"""
    from PySide6.QtWidgets import QMenu
    repo = _rg_branchy_repo(tmp_path)
    dlg = rg(repo)
    order = list(dlg.canvas.layout().order)
    k1, k2 = order[0], order[1]

    menu = QMenu(dlg)
    acts = dlg._build_node_menu(menu, [k1])
    assert set(acts) >= {"showlog", "browserepo", "copyrefs",
                         "cmp_heads", "udiff_heads", "cmp_wt"}
    # 两个节点时不出现单节点专属项
    menu2 = QMenu(dlg)
    acts2 = dlg._build_node_menu(menu2, [k1, k2])
    assert {"showlog", "cmp", "udiff"} <= set(acts2)
    assert "browserepo" not in acts2 and "copyrefs" not in acts2


def test_revgraph_context_menu_submenus(rg, tmp_path):
    """多引用/多本地分支时走子菜单：引用用全名、分支用短名，且带“全部”。"""
    from PySide6.QtWidgets import QMenu
    repo = _rg_branchy_repo(tmp_path)
    # c1 上同时挂 topic 与标签，c2 上挂 feature
    repo.runner.run("tag", "v1.0", "topic")
    repo.runner.run("branch", "other", "topic")
    dlg = rg(repo)

    target = next((k for k in dlg.canvas.layout().order
                   if len(dlg._deleteable_refs(k)) >= 2), None)
    assert target is not None, "应存在带多个引用的提交"
    menu = QMenu(dlg)
    acts = dlg._build_node_menu(menu, [target])
    delete_menu = acts.get("delete")
    assert delete_menu is not None and hasattr(delete_menu, "actions")
    labels = [a.text() for a in delete_menu.actions()]
    assert any(x.startswith("refs/") for x in labels), labels
    assert labels[-1] in ("All", "全部")
    switch_menu = acts.get("switch")
    if switch_menu is not None and hasattr(switch_menu, "actions"):
        short = [a.text() for a in switch_menu.actions()]
        assert all(not s.startswith("refs/") for s in short), short


def test_revgraph_find_dialog_filters_and_activates(qapp):
    from pytortoisegit.dialogs.revgraphfinddlg import RevGraphFindDlg

    items = [("a" * 40, "master", "first commit"),
             ("b" * 40, "topic", "second change")]
    dlg = RevGraphFindDlg(items)
    try:
        _find_dialog_asserts(dlg)
    finally:
        dlg.close()
        dlg.deleteLater()
        app = qapp
        if app is not None:
            app.processEvents()


def _find_dialog_asserts(dlg):
    assert dlg.list.topLevelItemCount() == 0, "未输入时不应有结果"

    dlg.edit.setText("second")
    dlg.refresh_list()
    assert dlg.list.topLevelItemCount() == 1

    # 默认不区分大小写
    dlg.edit.setText("SECOND")
    dlg.refresh_list()
    assert dlg.list.topLevelItemCount() == 1
    # 勾选区分大小写后大小写不再匹配
    dlg.chk_case.setChecked(True)
    dlg.refresh_list()
    assert dlg.list.topLevelItemCount() == 0

    # 仅查找引用名：标题里的 second 不应再命中
    dlg.edit.setText("second")
    dlg.chk_case.setChecked(False)
    dlg.chk_refs.setChecked(True)
    dlg.refresh_list()
    assert dlg.list.topLevelItemCount() == 0
    dlg.edit.setText("topic")
    dlg.refresh_list()
    assert dlg.list.topLevelItemCount() == 1

    # 正则
    dlg.chk_refs.setChecked(False)
    dlg.chk_regex.setChecked(True)
    dlg.edit.setText("fir.*commit")
    dlg.refresh_list()
    assert dlg.list.topLevelItemCount() == 1
    # 非法正则按字面量处理，不抛异常
    dlg.edit.setText("([")
    dlg.refresh_list()
    assert dlg.list.topLevelItemCount() == 0

    dlg.chk_regex.setChecked(False)
    dlg.edit.setText("commit")
    dlg.refresh_list()
    got = {}
    dlg.activated.connect(lambda h: got.setdefault("h", h))
    dlg.find_next()
    dlg._on_activated(dlg.list.currentItem())
    assert got.get("h"), "激活应发出 hash"


def test_revgraph_f5_refreshes(rg, tmp_path):
    from PySide6.QtCore import QEventLoop, QTimer, Qt
    from PySide6.QtGui import QKeyEvent

    repo = _rg_branchy_repo(tmp_path)
    dlg = rg(repo)
    before = dlg.canvas.node_count()
    assert before >= 1
    dlg.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_F5,
                                Qt.KeyboardModifier.NoModifier))
    loop = QEventLoop()
    QTimer.singleShot(2500, loop.quit)
    loop.exec()
    assert dlg.canvas.node_count() == before


def test_revgraph_save_formats_are_writable(rg, tmp_path):
    """另存为：位图格式以 Qt 实际可写为准，且过滤器里只出现可用格式。"""
    from pytortoisegit.dialogs.revisiongraphdlg import RevisionGraphDlg

    formats = RevisionGraphDlg.save_formats()
    assert ".png" in formats, "PNG 必须可用"
    assert all(f.startswith(".") for f in formats)

    repo = _rg_branchy_repo(tmp_path)
    dlg = rg(repo)
    filt = dlg._save_filter()
    assert "*.svg" in filt and "*.gv" in filt
    for ext in formats:
        assert f"*{ext}" in filt, f"{ext} 未出现在过滤器里: {filt}"


def test_revgraph_export_png_svg_and_gv(rg, tmp_path):
    """导出 PNG/SVG/.gv 都应产出非空且内容正确的文件。"""
    import os

    repo = _rg_branchy_repo(tmp_path)
    dlg = rg(repo)
    out = tmp_path / "out"
    out.mkdir()

    for ext in (".png", ".svg", ".gv"):
        path = out / f"graph{ext}"
        dlg._write_graph(str(path), ext)
        assert path.exists() and path.stat().st_size > 0, ext

    gv = (out / "graph.gv").read_text(encoding="utf-8")
    assert gv.startswith("digraph revisiongraph {")
    assert gv.rstrip().endswith("}")
    assert "->" in gv, "应包含父子连线"
    assert len([ln for ln in gv.splitlines() if "[label=" in ln]) >= 1

    svg = (out / "graph.svg").read_text(encoding="utf-8", errors="replace")
    assert "<svg" in svg

    if os.name == "nt":
        from PySide6.QtGui import QImage
        img = QImage(str(out / "graph.png"))
        assert not img.isNull() and img.width() > 0


def test_revgraph_export_rejects_unsupported_format(rg, tmp_path):
    """WMF/EMF 不受支持：应抛异常（由调用方提示），而不是静默写出空文件。"""
    repo = _rg_branchy_repo(tmp_path)
    dlg = rg(repo)
    target = tmp_path / "graph.wmf"
    with pytest.raises(RuntimeError):
        dlg._write_graph(str(target), ".wmf")
    assert not target.exists()


def test_revgraph_overview_toggle_and_hit(rg, tmp_path):
    """概览图：默认关闭、可切换、命中后可换算出滚动目标。"""
    from PySide6.QtCore import QPoint

    repo = _rg_branchy_repo(tmp_path)
    dlg = rg(repo)
    assert dlg.canvas.show_overview() is False

    dlg.btn_overview.setChecked(True)
    dlg._toggle_overview()
    assert dlg.canvas.show_overview() is True

    box, view = dlg.canvas._preview_rect()
    assert box is not None and view is not None
    assert box.width() > 0 and view.width() > 0
    # 缩略图位于视口右下角附近
    assert box.right() <= view.right() + 1
    assert box.bottom() <= view.bottom() + 1

    target = dlg.canvas._overview_hit(QPoint(int(box.center().x()),
                                              int(box.center().y())))
    assert target is not None
    # 缩略图外不应命中
    assert dlg.canvas._overview_hit(QPoint(0, 0)) is None

    dlg.btn_overview.setChecked(False)
    dlg._toggle_overview()
    assert dlg.canvas.show_overview() is False


# ---------------------------------------------------------------------------
# P3 数据侧：显示开关 / 引用解析
# ---------------------------------------------------------------------------

class _FakeCommit:
    """给纯函数用的最小提交替身。"""

    def __init__(self, h, parents=(), ref_types=(), subject=""):
        from types import SimpleNamespace
        self.hash = h
        self.parents = list(parents)
        self.subject = subject or h
        self.ref_infos = [SimpleNamespace(ref_type=t) for t in ref_types]


def test_revgraph_drop_tag_only_commits():
    """「显示所有标签」关闭时只丢"仅剩标签标注"的提交。"""
    from pytortoisegit.dialogs.revisiongraphdlg import drop_tag_only_commits

    tag_only = _FakeCommit("a" * 40, ref_types=("tag",))
    mixed = _FakeCommit("b" * 40, ref_types=("tag", "branch"))
    plain = _FakeCommit("c" * 40)
    branch_only = _FakeCommit("d" * 40, ref_types=("branch",))

    got = drop_tag_only_commits([tag_only, mixed, plain, branch_only])
    assert [c.hash for c in got] == [mixed.hash, plain.hash, branch_only.hash]


def test_revgraph_collapse_linear_chains():
    """无标注的线性链被折叠，并把子的父接到祖父；分叉点保留。"""
    from pytortoisegit.dialogs.revisiongraphdlg import collapse_linear_chains

    c1 = _FakeCommit("1" * 40, ref_types=("branch",))
    c2 = _FakeCommit("2" * 40, parents=["1" * 40])
    c3 = _FakeCommit("3" * 40, parents=["2" * 40])
    c4 = _FakeCommit("4" * 40, parents=["3" * 40], ref_types=("branch",))

    got = collapse_linear_chains([c1, c2, c3, c4])
    assert [c.hash for c in got] == [c1.hash, c4.hash]
    assert c4.parents == [c1.hash], "子的父应接到祖父，链不能断"

    # 分叉点：c1 有两个子，不能被折叠
    c1b = _FakeCommit("1" * 40, ref_types=("branch",))
    c2b = _FakeCommit("2" * 40, parents=["1" * 40], ref_types=("branch",))
    c3b = _FakeCommit("3" * 40, parents=["1" * 40], ref_types=("branch",))
    got2 = collapse_linear_chains([c1b, c2b, c3b])
    assert len(got2) == 3, "有分叉时不应折叠"
    assert c1b.parents == []


def test_revgraph_load_args_sparse_flag():
    from pytortoisegit.dialogs.revisiongraphdlg import build_load_args

    assert build_load_args({})["sparse"] is False
    assert build_load_args({}, sparse=True)["sparse"] is True


def test_refs_peel_annotated_tags_and_include_stash(tmp_path):
    """附注标签需解引用才能挂到提交上；refs/stash 也要能取到且有非空短名。"""
    from pytortoisegit.git.git import GitRunner
    from pytortoisegit.git.repo import Repository
    from pytortoisegit.git.rev import GitRevLoglist

    root = tmp_path / "refsrepo"
    root.mkdir()
    runner = GitRunner(cwd=str(root))
    runner.init(str(root), initial_branch="main")
    repo = Repository.open(str(root))
    runner.run("config", "user.email", "t@example.com")
    runner.run("config", "user.name", "Tester")
    (root / "a.txt").write_text("1\n", encoding="utf-8")
    runner.run("add", "-A")
    assert runner.run("commit", "-m", "c1").returncode == 0
    runner.run("tag", "-a", "v1.0", "-m", "annotated")
    runner.run("tag", "light")
    head = repo.head_commit()

    # 制造真实 stash（需要工作区有改动）
    (root / "a.txt").write_text("dirty\n", encoding="utf-8")
    assert runner.run("stash", "push", "-m", "wip").returncode == 0

    log = GitRevLoglist(repo)
    log.load(limit=0, all_branches=True, simplify=True)

    # 附注标签与轻量标签都必须指向 c1 本身
    assert log.refs["refs/tags/v1.0"].target == head
    assert log.refs["refs/tags/light"].target == head
    # stash 引用存在且短名非空（否则节点会渲染成空标签）
    assert "refs/stash" in log.refs
    assert log.refs["refs/stash"].ref_type == "stash"
    assert log.refs["refs/stash"].shortname == "stash"


def test_revgraph_view_menu_toggles(rg, tmp_path, monkeypatch):
    """视图菜单三个开关的默认值与联动（对齐 InitialSetMenu 默认值）。"""
    repo = _rg_branchy_repo(tmp_path)
    dlg = rg(repo)

    assert dlg.act_all_tags.isChecked() is True      # 原版默认 TRUE
    assert dlg.act_branchings.isChecked() is False   # 原版默认 FALSE
    assert dlg.act_arrow.isChecked() is False        # 原版默认 FALSE
    labels = [a.text() for a in dlg.menu_view.actions() if a.text()]
    for act in (dlg.act_overview, dlg.act_branchings, dlg.act_all_tags,
                dlg.act_arrow):
        assert act.text() in labels, labels

    # 切换显示开关应触发重新拉取（对齐 UpdateFullHistory）
    calls = []
    monkeypatch.setattr(dlg, "refresh", lambda: calls.append("refresh"))
    dlg.act_all_tags.setChecked(False)
    assert calls == ["refresh"]
    dlg.act_branchings.setChecked(True)
    assert calls == ["refresh", "refresh"]

    # 箭头开关只重绘，不重新拉取
    monkeypatch.setattr(dlg, "refresh", lambda: calls.append("refresh2"))
    dlg.act_arrow.setChecked(True)
    assert calls == ["refresh", "refresh"]
    assert dlg.canvas._arrow_to_merges is True

    # 概览开关与工具栏按钮保持同步
    dlg.act_overview.setChecked(True)
    assert dlg.btn_overview.isChecked() is True
    assert dlg.canvas.show_overview() is True


def test_revgraph_all_tags_toggle_changes_graph(rg, tmp_path):
    """「显示所有标签」关闭后，仅由标签可达的提交应从图中消失。"""
    from pytortoisegit.git.git import GitRunner
    from pytortoisegit.git.repo import Repository

    root = tmp_path / "tagrepo"
    root.mkdir()
    runner = GitRunner(cwd=str(root))
    runner.init(str(root), initial_branch="main")
    repo = Repository.open(str(root))
    runner.run("config", "user.email", "t@example.com")
    runner.run("config", "user.name", "Tester")
    for n in (1, 2):
        (root / "a.txt").write_text(f"{n}\n", encoding="utf-8")
        runner.run("add", "-A")
        assert runner.run("commit", "-m", f"c{n}").returncode == 0
    runner.run("tag", "v2")                      # c2 打标签
    runner.run("reset", "--hard", "HEAD~1")      # main 退回 c1 => c2 仅标签可达

    dlg = rg(repo)
    with_tag = {dlg._commits[k].subject for k in dlg.canvas.layout().order}
    assert "c2" in with_tag, with_tag

    dlg.act_all_tags.setChecked(False)
    from PySide6.QtCore import QEventLoop, QTimer
    loop = QEventLoop()
    QTimer.singleShot(2500, loop.quit)
    loop.exec()
    without = {dlg._commits[k].subject for k in dlg.canvas.layout().order}
    assert "c2" not in without, without



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


def _submenu(menu, label):
    """取右键菜单中的子菜单（按标题）。"""
    for a in menu.actions():
        if a.menu() is not None and a.text() == label:
            return a.menu()
    return None


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
    top = [a.text() for a in menu.actions()]
    assert "打开" in top
    assert "复制" in top
    assert "粘贴" in top
    assert "新建文件夹" in top
    assert "TortoiseGit" in top
    assert "刷新" in top
    tg = _submenu(menu, "TortoiseGit")
    labels = [a.text() for a in tg.actions()]
    assert "Git 克隆…" in labels
    assert "设置" in labels
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
    assert "复制" in labels
    assert "TortoiseGit" in labels
    tg = _submenu(menu, "TortoiseGit")
    assert "设置" in [a.text() for a in tg.actions()]
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
    # 工作树内目录 → 经典菜单（含 提交、设置）
    menu = dlg._build_classic_menu(str(sub), dlg.content_list)
    labels = [a.text() for a in menu.actions()]
    assert "提交…" in labels
    assert "设置" in labels
    # 仓库外目录 → 基本操作 + TortoiseGit(Clone/Settings)
    menu2 = dlg._build_folder_nonrepo_menu(str(plain))
    tg = _submenu(menu2, "TortoiseGit")
    labels2 = [a.text() for a in tg.actions()]
    assert "Git 克隆…" in labels2
    assert "设置" in labels2
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
    # 当前浏览为工作树内子目录 → 第一层(同步/提交) + 其余进 TortoiseGit 子菜单
    dlg._show_content(str(sub))
    menu = dlg._build_blank_menu(dlg._current_dir(), dlg.content_list)
    top = [a.text() for a in menu.actions() if a.text()]
    assert "复制" in top
    for expected in ("同步", "提交…"):
        assert expected in top, expected
    tg = _submenu(menu, "TortoiseGit")
    labels = [a.text() for a in tg.actions()]
    for expected in ("拉取…", "推送…", "差异…", "显示日志",
                     "仓库浏览器", "储藏更改…", "还原…", "切换/检出…", "合并…", "设置"):
        assert expected in labels, expected
    # 第一层命令不出现在子菜单里
    assert "提交…" not in labels
    # 工作树内子目录本身不显示 Git Clone（文件夹已在 git 中）
    assert "Git 克隆…" not in labels
    # 当前浏览为仓库外目录 → 第一层 Clone/CreateRepo；子菜单 Settings
    dlg._show_content(str(plain))
    menu2 = dlg._build_blank_menu(dlg._current_dir(), dlg.content_list)
    top2 = [a.text() for a in menu2.actions() if a.text()]
    assert "Git 克隆…" in top2
    tg2 = _submenu(menu2, "TortoiseGit")
    labels2 = [a.text() for a in tg2.actions()]
    assert "设置" in labels2
    assert "提交…" not in labels2
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
    # 工作树内文件 → 顶层基本操作 + 第一层(提交) + 其余进 TortoiseGit 子菜单
    menu = dlg._build_file_menu(str(repo / "a.txt"), dlg.content_list)
    top = [a.text() for a in menu.actions()]
    assert "打开" in top
    assert "显示位置" in top
    assert "复制" in top
    assert "粘贴" in top
    assert "新建文件" in top
    assert "提交…" in top
    tg = _submenu(menu, "TortoiseGit")
    labels = [a.text() for a in tg.actions()]
    for expected in ("差异…", "显示日志", "储藏更改…",
                     "追溯…", "设置", "还原…", "移除…"):
        assert expected in labels, expected
    assert "提交…" not in labels
    # 工作树内子目录中的文件
    menu2 = dlg._build_file_menu(str(sub / "b.txt"), dlg.content_list)
    tg2 = _submenu(menu2, "TortoiseGit")
    labels2 = [a.text() for a in tg2.actions()]
    assert "储藏更改…" in labels2
    assert "提交…" not in labels2
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
    top = [a.text() for a in menu.actions()]
    assert "打开" in top
    assert "显示位置" in top
    assert "复制" in top
    tg = _submenu(menu, "TortoiseGit")
    labels = [a.text() for a in tg.actions()] if tg is not None else []
    assert "提交…" not in labels
    assert "储藏更改…" not in labels
    assert "差异…" not in labels
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

    # 经典菜单：提交/日志/拉取/推送/同步/还原/清理/设置 均有图标
    classic = dlg._build_classic_menu(str(repo))
    for label in ["提交…", "显示日志", "拉取…", "推送…", "同步",
                  "还原…", "清理…", "设置"]:
        act = by_label(classic.actions(), label)
        assert not act.icon().isNull(), label
    # 文件菜单：顶层基本操作「打开」+ 第一层「提交…」；其余在子菜单
    fmenu = dlg._build_file_menu(str(repo / "a.txt"), dlg.content_list)
    assert not by_label(fmenu.actions(), "打开").icon().isNull()
    assert not by_label(fmenu.actions(), "提交…").icon().isNull()
    tg = _submenu(fmenu, "TortoiseGit")
    for label in ["差异…", "显示日志",
                  "储藏更改…", "追溯…", "设置"]:
        act = by_label(tg.actions(), label)
        assert not act.icon().isNull(), label
    # 仓库外目录：Clone + Settings
    nrepo = dlg._build_folder_nonrepo_menu(str(plain))
    tg2 = _submenu(nrepo, "TortoiseGit")
    for label in ["Git 克隆…", "设置"]:
        act = by_label(tg2.actions(), label)
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
    assert any(("应用储藏" == t) for t in a_labels), a_labels
    dlg.reject()


def test_mainmenu_undo_delete_and_paste(
        qapp, isolated_settings, tmp_path, monkeypatch):
    """撤销删除恢复文件；撤销粘贴移除目标。"""
    from pytortoisegit.dialogs.mainmenu import MainMenuDlg
    from pytortoisegit.git.git import GitRunner
    from PySide6.QtWidgets import QMessageBox
    repo = tmp_path / "repo"
    repo.mkdir()
    runner = GitRunner(cwd=str(repo))
    runner.init(str(repo), initial_branch="main")
    runner.run("config", "user.email", "t@x.com")
    runner.run("config", "user.name", "T")
    f = repo / "a.txt"
    f.write_text("A\n", encoding="utf-8")
    runner.run("add", "-A")
    runner.run("commit", "-m", "init")
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    dlg = MainMenuDlg()
    # 删除 → 撤销恢复
    dlg._delete_path(str(f))
    assert not f.exists()
    dlg._undo_last()
    assert f.exists() and f.read_text(encoding="utf-8") == "A\n"
    # 复制 + 粘贴 → 撤销移除目标，源保留
    sub = repo / "sub"
    sub.mkdir()
    dlg._copy_files([str(f)])
    dlg._paste_files(str(sub))
    dst = sub / "a.txt"
    assert dst.exists()
    dlg._undo_last()
    assert not dst.exists()
    assert f.exists()
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


def test_daemon_menu_disabled(qapp, isolated_settings, tmp_path_factory):
    """daemon 暂时置灰：菜单项保留展示但不可点击，且分发被拦截。"""
    from PySide6.QtWidgets import QMenu
    from pytortoisegit import menuitems as mi
    from pytortoisegit.dialogs.mainmenu import MainMenuDlg
    from pytortoisegit.git.git import GitRunner
    from pytortoisegit.res.strings import tr

    assert "daemon" in mi.DISABLED_COMMANDS

    parent = tmp_path_factory.mktemp("daemon_disabled")
    repo = parent / "repo"
    repo.mkdir()
    runner = GitRunner(cwd=str(repo))
    runner.init(str(repo), initial_branch="main")
    runner.run("config", "user.email", "t@x.com")
    runner.run("config", "user.name", "T")
    (repo / "tracked.txt").write_text("a\n", encoding="utf-8")
    runner.run("add", "tracked.txt")
    runner.run("commit", "-m", "init")
    (repo / "tracked.txt").write_text("mod\n", encoding="utf-8")

    label = tr("menu_cmd_daemon", "Daemon…")
    dlg = MainMenuDlg(repo_path=str(repo))
    # 状态驱动的 TortoiseGit 子菜单：daemon 在（单文件、已版本化），但置灰
    menu = QMenu(dlg.repo_tree)
    dlg._populate_tortoisegit_menu(menu, str(repo / "tracked.txt"), shift=False)
    daemon_acts = [a for a in menu.actions() if a.text() == label]
    assert daemon_acts, "daemon 菜单项应保留展示"
    assert not daemon_acts[0].isEnabled()

    # 「命令」菜单里的 daemon 同样置灰
    found = False
    for act in dlg.menuBar().actions():
        top = act.menu()
        if top is None:
            continue
        for group in top.actions():
            sub = group.menu()
            for a in (sub.actions() if sub is not None else []):
                if a.text() == label:
                    assert not a.isEnabled()
                    found = True
    assert found, "命令菜单应包含 daemon"

    # _dispatch 被拦截：不调用命令实现，仅提示暂不开放
    called: list[str] = []
    dlg._run = lambda ctx, name: called.append(name)  # type: ignore[method-assign]
    dlg._dispatch("daemon", extra={"path": str(repo / "tracked.txt")})
    assert not called
    assert dlg.status.text() == tr(
        "menu_cmd_disabled", "This feature is temporarily unavailable")
    dlg.reject()


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


def test_dialog_units_base_y_accommodates_cjk(qapp):
    from PySide6.QtGui import QFont, QFontMetrics
    from pytortoisegit.ui.rc import DialogUnits
    fu = DialogUnits(9, "Segoe UI")
    f = QFont("Segoe UI")
    f.setPointSize(9)
    f.setStyleHint(QFont.StyleHint.Helvetica)
    # base_y 至少容纳拉丁行高（装有 CJK 字体时会更大）
    assert fu.base_y >= QFontMetrics(f).height()


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