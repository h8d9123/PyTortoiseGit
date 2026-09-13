"""E2E：远程同步（TC-SYNC / TC-PULL / TC-PUSH / TC-FETCH / TC-REMOTE / TC-REQPULL）。

使用本地 bare 仓库作为 origin，验证真实网络无关的同步行为。

运行：QT_QPA_PLATFORM=offscreen python -m pytest test/test_e2e_remote.py -v
"""

from pathlib import Path

from PySide6.QtWidgets import QDialog


def _remote_new_commit(remote_repo):
    """从 bare 再克隆一份，提交并推送，使 origin 领先 local。"""
    from pytortoisegit.git.git import GitRunner
    other = remote_repo.bare.parent / "other"
    GitRunner(cwd=str(remote_repo.bare.parent)).run(
        "clone", str(remote_repo.bare), str(other))
    orun = GitRunner(cwd=str(other))
    orun.run("config", "user.email", "other@example.com")
    orun.run("config", "user.name", "Other")
    (other / "a.txt").write_text("remote change\n", encoding="utf-8")
    orun.run("add", "-A")
    orun.run("commit", "-m", "remote change")
    assert orun.run("push", "origin", "main").returncode == 0
    return GitRunner(cwd=str(remote_repo.bare)).run(
        "rev-parse", "main").stdout.strip()


def test_TC_SYNC_001_state(qapp, ui, remote_repo):
    """Sync 对话框展示本地/远程分支状态。"""
    from pytortoisegit.dialogs.sync import SyncDlg
    dlg = SyncDlg(remote_repo.local)
    dlg.show()
    items = [dlg.local_combo.itemText(i) for i in range(dlg.local_combo.count())]
    assert "main" in items
    assert dlg.remote_combo.count() >= 1


def test_TC_PULL_001_updates_local(qapp, ui, remote_repo, auto_progress):
    """Pull → 本地更新到远程。"""
    from pytortoisegit.dialogs.pulldlg import PullFetchDlg
    remote_head = _remote_new_commit(remote_repo)
    dlg = PullFetchDlg(remote_repo.local, fetch_only=False)
    dlg.show()
    ui.click(dlg.btn_ok)
    assert dlg.result() == QDialog.DialogCode.Accepted
    assert remote_repo.runner.run("rev-parse", "HEAD").stdout.strip() == remote_head


def test_TC_PULL_002_no_commit(qapp, ui, remote_repo, auto_progress):
    """Pull 勾选“不提交” → 合并但不产生提交（HEAD 不变，改动已暂存）。"""
    from pathlib import Path
    from pytortoisegit.dialogs.pulldlg import PullFetchDlg
    _remote_new_commit(remote_repo)                      # origin 领先
    root = Path(remote_repo.local.root)
    (root / "b.txt").write_text("local\n", encoding="utf-8")
    remote_repo.runner.run("add", "-A")                  # 本地分叉提交
    remote_repo.runner.run("commit", "-m", "local change")
    local_head = remote_repo.runner.run("rev-parse", "HEAD").stdout.strip()
    dlg = PullFetchDlg(remote_repo.local, fetch_only=False)
    dlg.chk_nocommit.setChecked(True)
    dlg.show()
    ui.click(dlg.btn_ok)
    assert remote_repo.runner.run("rev-parse", "HEAD").stdout.strip() == local_head
    # 合并结果已进入工作区
    assert (root / "a.txt").read_text(encoding="utf-8") == "remote change\n"


def test_TC_FETCH_001_updates_remote_tracking(qapp, ui, remote_repo, auto_progress):
    """Fetch → 远程跟踪更新，本地分支不变。"""
    from pytortoisegit.dialogs.pulldlg import PullFetchDlg
    remote_head = _remote_new_commit(remote_repo)
    local_head = remote_repo.runner.run("rev-parse", "HEAD").stdout.strip()
    dlg = PullFetchDlg(remote_repo.local, fetch_only=True)
    dlg.show()
    ui.click(dlg.btn_ok)
    assert remote_repo.runner.run(
        "rev-parse", "origin/main").stdout.strip() == remote_head
    assert remote_repo.runner.run("rev-parse", "HEAD").stdout.strip() == local_head


def test_TC_PUSH_001_updates_remote(qapp, ui, remote_repo, auto_progress, monkeypatch):
    """Push → 远程分支更新。"""
    from pytortoisegit.cmdline import parse
    from pytortoisegit.commands.dispatcher import CommandContext
    from pytortoisegit.commands.push import push
    from pytortoisegit.dialogs.pushdlg import PushDlg
    (Path(remote_repo.local.root) / "a.txt").write_text(
        "local new\n", encoding="utf-8")
    remote_repo.runner.run("add", "-A")
    remote_repo.runner.run("commit", "-m", "local new")
    local_head = remote_repo.runner.run("rev-parse", "HEAD").stdout.strip()

    def fake_exec(self):
        self._on_ok()
        return self.result()

    monkeypatch.setattr(PushDlg, "exec", fake_exec)
    cl = parse(["/command:push", f"/path:{remote_repo.local.root}"])
    assert push(CommandContext(cl=cl)) == "ok"
    from pytortoisegit.git.git import GitRunner
    assert GitRunner(cwd=str(remote_repo.bare)).run(
        "rev-parse", "main").stdout.strip() == local_head


def test_TC_REMOTE_001_add_remote(qapp, ui, git_repo):
    """AddRemote → git remote -v 出现该远程。"""
    from pytortoisegit.dialogs.addremotedlg import AddRemoteDlg
    dlg = AddRemoteDlg(git_repo)
    ui.set_text(dlg.name_edit, "upstream")
    ui.set_text(dlg.url_edit, "https://example.com/repo.git")
    dlg.show()
    ui.click(dlg.btn_ok)
    assert dlg.result() == QDialog.DialogCode.Accepted
    assert "upstream" in git_repo.runner.run("remote").stdout


def test_TC_REQPULL_001_accepts(qapp, ui, git_repo, auto_progress):
    """RequestPull → 确认后接受（生成请求）。"""
    from pytortoisegit.dialogs.requestpulldlg import RequestPullDlg
    dlg = RequestPullDlg(git_repo)
    dlg.show()
    ui.click(dlg.btn_ok)
    assert dlg.result() == QDialog.DialogCode.Accepted


def test_TC_FLOW_001_pull_stash_rebase_pop(qapp, ui, remote_repo, auto_progress):
    """验证 pull + stash + rebase + stash pop 组合流程目前是否支持。

    流程（本地有未提交改动、远端同时前进时最典型的做法）：
      1. 工作区改动 → stash
      2. pull --rebase（等价 rebase 到远端）
      3. stash pop 恢复本地改动
    断言：远端提交已并入、本地改动恢复、历史线性（无 merge 提交）。
    """
    from pathlib import Path
    from pytortoisegit.git.stash import GitStash
    from pytortoisegit.dialogs.pulldlg import PullFetchDlg

    local = remote_repo.local
    root = Path(local.root)
    runner = remote_repo.runner

    # 准备一个已跟踪文件并推送到远端
    (root / "b.txt").write_text("b1\n", encoding="utf-8")
    assert runner.run("add", "b.txt").returncode == 0
    assert runner.run("commit", "-m", "add b").returncode == 0
    assert runner.run("push", "origin", "main").returncode == 0

    # 1) 本地未提交改动 → stash（pull 前要求工作区干净）
    (root / "b.txt").write_text("b1\nlocal change\n", encoding="utf-8")
    stash = GitStash(local)
    assert stash.create("wip") is True, "stash 失败"
    assert (root / "b.txt").read_text(encoding="utf-8") == "b1\n"

    # 远端前进（修改另一个文件 a.txt）
    remote_head = _remote_new_commit(remote_repo)

    # 2) pull --rebase（= rebase 到远端）
    dlg = PullFetchDlg(local, fetch_only=False)
    dlg.chk_rebase.setChecked(True)
    dlg.show()
    ui.click(dlg.btn_ok)
    assert local.run("rev-parse", "HEAD").stdout.strip() == remote_head, \
        "pull --rebase 未更新到远端 HEAD"

    # 3) stash pop 恢复本地改动
    entry = stash.latest()
    assert entry is not None, "stash 列表为空"
    assert stash.pop(entry.gd) is True, "stash pop 失败"
    assert "local change" in (root / "b.txt").read_text(encoding="utf-8"), \
        "stash pop 未恢复本地改动"

    # 线性历史（无 merge 提交）
    assert runner.run("rev-list", "--merges", "HEAD").stdout.strip() == "", \
        "pull --rebase 后不应产生 merge 提交"
