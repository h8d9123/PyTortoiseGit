"""对常用子窗口截图（离线渲染，不需要显示器）。

默认跳过；需要生成时设置环境变量：

    PYTG_SCREENSHOTS=1 QT_QPA_PLATFORM=offscreen \
        python -m pytest test/test_e2e_screenshots.py -v

可选自定义输出目录：

    PYTG_SCREENSHOT_DIR=/tmp/shots PYTG_SCREENSHOTS=1 python -m pytest test/test_e2e_screenshots.py

输出：<仓库根>/screenshots/*.png
"""

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("PYTG_SCREENSHOTS"),
    reason="设置 PYTG_SCREENSHOTS=1 生成子窗口截图")

SHOT_DIR = Path(os.environ.get(
    "PYTG_SCREENSHOT_DIR",
    Path(__file__).resolve().parents[1] / "screenshots"))


@pytest.fixture
def shot_repo(git_repo):
    """准备有分支/标签/改动/stash 的仓库，让列表类窗口有内容。"""
    from pathlib import Path as _P
    root = _P(git_repo.root)
    (root / "a.txt").write_text("line1\nsecond\nline3\n", encoding="utf-8")
    git_repo.runner.run("add", "-A")
    git_repo.runner.run("commit", "-m", "second commit")
    git_repo.runner.run("branch", "feature")
    git_repo.runner.run("tag", "v1.0")
    (root / "a.txt").write_text("line1\ndirty\nline3\n", encoding="utf-8")
    (root / "new.txt").write_text("untracked\n", encoding="utf-8")
    git_repo.runner.run("stash", "push", "-m", "sample stash")
    return git_repo


def _capture(ui, name, factory, wait_for=None):
    dlg = factory()
    dlg.show()
    ui.wait(150)
    if wait_for is not None:
        ui.wait_until(lambda: wait_for(dlg), timeout_ms=5000)
    ui.wait(120)
    path = SHOT_DIR / f"{name}.png"
    saved = dlg.grab().save(str(path))
    dlg.close()
    ui.wait(30)
    assert saved, f"截图保存失败: {path}"
    return path, dlg


def test_capture_common_dialogs(qapp, ui, shot_repo, tmp_path):
    """依次打开常用子窗口并截图到 SHOT_DIR。"""
    from pytortoisegit.dialogs.aboutdlg import AboutDlg
    from pytortoisegit.dialogs.adddlg import AddDlg
    from pytortoisegit.dialogs.addremotedlg import AddRemoteDlg
    from pytortoisegit.dialogs.applypatchdlg import ApplyPatchDlg
    from pytortoisegit.dialogs.blamedlg import BlameDlg
    from pytortoisegit.dialogs.browserefs import BrowseRefsDlg
    from pytortoisegit.dialogs.cleandlg import CleanDlg
    from pytortoisegit.dialogs.clonedlg import CloneDlg
    from pytortoisegit.dialogs.commitdlg import CommitDlg
    from pytortoisegit.dialogs.createbranchdlg import CreateBranchDlg, CreateTagDlg
    from pytortoisegit.dialogs.createrepoldg import CreateRepoDlg
    from pytortoisegit.dialogs.diffdlg import DiffDlg
    from pytortoisegit.dialogs.exportdlg import ExportDlg
    from pytortoisegit.dialogs.formatpatchdlg import FormatPatchDlg
    from pytortoisegit.dialogs.gitswitchdlg import GitSwitchDlg
    from pytortoisegit.dialogs.ignoredlg import IgnoreDlg
    from pytortoisegit.dialogs.inputdlg import InputDlg, UrlDlg
    from pytortoisegit.dialogs.logdlg import LogDlg
    from pytortoisegit.dialogs.mergedlg import MergeDlg
    from pytortoisegit.dialogs.pulldlg import PullFetchDlg
    from pytortoisegit.dialogs.pushdlg import PushDlg
    from pytortoisegit.dialogs.reflogdlg import ReflogDlg
    from pytortoisegit.dialogs.renamedlg import RenameDlg
    from pytortoisegit.dialogs.repobrowserdlg import RepositoryBrowserDlg
    from pytortoisegit.dialogs.requestpulldlg import RequestPullDlg
    from pytortoisegit.dialogs.resetdlg import ResetDlg
    from pytortoisegit.dialogs.revertdlg import RevertDlg
    from pytortoisegit.dialogs.revisiongraphdlg import RevisionGraphDlg
    from pytortoisegit.dialogs.selectremoterefdlg import SelectRemoteRefDlg
    from pytortoisegit.dialogs.settingsdlg import SettingsDlg
    from pytortoisegit.dialogs.stashdlg import StashDlg
    from pytortoisegit.dialogs.statgraphdlg import StatGraphDlg
    from pytortoisegit.dialogs.sync import SyncDlg
    from pytortoisegit.dialogs.worktreecreatedlg import WorktreeCreateDlg
    from pytortoisegit.dialogs.worktreelistdlg import WorktreeListDlg

    repo = shot_repo
    shot = SHOT_DIR
    shot.mkdir(parents=True, exist_ok=True)

    # (文件名, 构造, 等待条件)
    entries = [
        ("01-about", lambda: AboutDlg(), None),
        ("02-clone", lambda: CloneDlg("https://github.com/user/repo.git"), None),
        ("03-commit", lambda: CommitDlg(repo),
         lambda d: d.status_tree.topLevelItemCount() > 0),
        ("04-log", lambda: LogDlg(repo),
         lambda d: d.tree.topLevelItemCount() > 0),
        ("05-diff", lambda: DiffDlg(repo, "HEAD~1", "HEAD"),
         lambda d: d.file_tree.topLevelItemCount() > 0),
        ("06-blame", lambda: BlameDlg(repo, "a.txt"),
         lambda d: d.table.rowCount() > 0),
        ("07-browserefs", lambda: BrowseRefsDlg(repo),
         lambda d: d.tree.topLevelItemCount() > 0),
        ("08-switch", lambda: GitSwitchDlg(repo), None),
        ("09-branch", lambda: CreateBranchDlg(repo), None),
        ("10-tag", lambda: CreateTagDlg(repo), None),
        ("11-reflog", lambda: ReflogDlg(repo),
         lambda d: d.table.rowCount() > 0),
        ("12-reset", lambda: ResetDlg(repo), None),
        ("13-revert", lambda: RevertDlg(repo), None),
        ("14-clean", lambda: CleanDlg(repo), None),
        ("15-add", lambda: AddDlg(repo), None),
        ("16-ignore", lambda: IgnoreDlg(repo, paths=["new.txt"]), None),
        ("17-rename", lambda: RenameDlg(repo, ["a.txt"]), None),
        ("18-stash", lambda: StashDlg(repo), None),
        ("19-export", lambda: ExportDlg(repo), None),
        ("20-formatpatch", lambda: FormatPatchDlg(repo), None),
        ("21-applypatch", lambda: ApplyPatchDlg(repo, patches=["a.patch"]), None),
        ("22-sync", lambda: SyncDlg(repo), None),
        ("23-pull", lambda: PullFetchDlg(repo, fetch_only=False), None),
        ("24-fetch", lambda: PullFetchDlg(repo, fetch_only=True), None),
        ("25-push", lambda: PushDlg(repo), None),
        ("26-addremote", lambda: AddRemoteDlg(repo), None),
        ("27-selectref", lambda: SelectRemoteRefDlg(repo, remote="origin"), None),
        ("28-requestpull", lambda: RequestPullDlg(repo), None),
        ("29-merge", lambda: MergeDlg(repo), None),
        ("30-repobrowser", lambda: RepositoryBrowserDlg(repo),
         lambda d: d.list.topLevelItemCount() > 0),
        ("31-revisiongraph", lambda: RevisionGraphDlg(repo), None),
        ("32-statgraph", lambda: StatGraphDlg(repo), None),
        ("33-worktreelist", lambda: WorktreeListDlg(repo),
         lambda d: d.tree.topLevelItemCount() > 0),
        ("34-worktreecreate", lambda: WorktreeCreateDlg(repo), None),
        ("35-settings", lambda: SettingsDlg(repo), None),
        ("36-url", lambda: UrlDlg(initial="https://github.com/u/r.git"), None),
        ("37-input", lambda: InputDlg(hint="message:", text="hello"), None),
        ("38-createrepo", lambda: CreateRepoDlg(str(tmp_path / "newrepo")), None),
    ]

    captured = []
    errors = []
    keep_alive = []  # 持有引用，避免循环中途析构图形窗口导致崩溃
    for name, factory, wait_for in entries:
        try:
            path, dlg = _capture(ui, name, factory, wait_for)
            captured.append(path)
            keep_alive.append(dlg)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{name}: {exc}")

    print(f"\n截图目录: {shot}")
    print(f"成功 {len(captured)} 张，失败 {len(errors)} 个")
    for e in errors:
        print("  FAIL", e)
    assert not errors, errors
