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
