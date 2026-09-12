"""E2E：暂存 Stash（TC-STASH）。

运行：QT_QPA_PLATFORM=offscreen python -m pytest test/test_e2e_stash.py -v
"""

from pathlib import Path

import pytest
from PySide6.QtWidgets import QDialog, QMessageBox


def _dirty(repo):
    (Path(repo.root) / "a.txt").write_text("dirty\n", encoding="utf-8")


def _stash_count(repo):
    out = repo.runner.run("stash", "list").stdout or ""
    return len([x for x in out.splitlines() if x.strip()])


def test_TC_STASH_001_save_with_message(qapp, ui, git_repo, auto_progress, monkeypatch):
    """保存 stash（含消息）→ stash 生成，工作区干净。"""
    from pytortoisegit.dialogs.stashdlg import StashDlg
    from pytortoisegit.cmdline import parse
    from pytortoisegit.commands.dispatcher import CommandContext
    from pytortoisegit.commands.stash import stash
    _dirty(git_repo)

    def fake_exec(self):
        self.msg_edit.setText("e2e stash")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(StashDlg, "exec", fake_exec)
    cl = parse(["/command:stash", f"/path:{git_repo.root}"])
    assert stash(CommandContext(cl=cl)) == "ok"
    assert "e2e stash" in git_repo.runner.run("stash", "list").stdout
    assert git_repo.runner.run("status", "--porcelain").stdout.strip() == ""


def test_TC_STASH_002_include_untracked_warning(qapp, ui, git_repo, monkeypatch):
    """勾选 include untracked → 确认警告，选是才继续。"""
    from pytortoisegit.dialogs.stashdlg import StashDlg
    _dirty(git_repo)
    dlg = StashDlg(git_repo)
    dlg.untracked_box.setChecked(True)
    monkeypatch.setattr(QMessageBox, "warning",
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    ui.click(dlg._ok_btn)
    assert dlg.result() == QDialog.DialogCode.Accepted
    assert dlg.include_untracked


def test_TC_STASH_002b_include_untracked_cancel(qapp, ui, git_repo, monkeypatch):
    """include untracked 警告选否 → 不关闭。"""
    from pytortoisegit.dialogs.stashdlg import StashDlg
    _dirty(git_repo)
    dlg = StashDlg(git_repo)
    dlg.untracked_box.setChecked(True)
    monkeypatch.setattr(QMessageBox, "warning",
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))
    ui.click(dlg._ok_btn)
    assert dlg.result() != QDialog.DialogCode.Accepted


def test_TC_STASH_003_all_mutual_exclusion(qapp, ui, git_repo):
    """--all 与 include untracked 互斥。"""
    from pytortoisegit.dialogs.stashdlg import StashDlg
    dlg = StashDlg(git_repo)
    dlg.all_box.setChecked(True)
    assert not dlg.untracked_box.isChecked()
    assert not dlg.untracked_box.isEnabled()


def test_TC_STASH_004_list(qapp, git_repo, monkeypatch):
    """查看 stash 列表 → 弹出信息含条目。"""
    from pytortoisegit.cmdline import parse
    from pytortoisegit.commands.dispatcher import CommandContext
    from pytortoisegit.commands.stashlist import stashlist
    _dirty(git_repo)
    git_repo.runner.run("stash", "push", "-m", "listed stash")
    captured = {}
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: captured.__setitem__("t", a[2])))
    cl = parse(["/command:stashlist", f"/path:{git_repo.root}"])
    assert stashlist(CommandContext(cl=cl)) == "ok"
    assert "listed stash" in captured["t"]


def test_TC_STASH_005_apply(qapp, git_repo):
    """stash apply → 改动恢复，stash 仍在。"""
    from pytortoisegit.cmdline import parse
    from pytortoisegit.commands.dispatcher import CommandContext
    from pytortoisegit.commands.stashapply import stashapply
    _dirty(git_repo)
    git_repo.runner.run("stash", "push", "-m", "apply me")
    cl = parse(["/command:stashapply", f"/path:{git_repo.root}"])
    assert stashapply(CommandContext(cl=cl)) == "ok"
    assert (Path(git_repo.root) / "a.txt").read_text() == "dirty\n"
    assert _stash_count(git_repo) == 1


def test_TC_STASH_006_pop(qapp, git_repo):
    """stash pop → 改动恢复且该 stash 删除。"""
    from pytortoisegit.cmdline import parse
    from pytortoisegit.commands.dispatcher import CommandContext
    from pytortoisegit.commands.stashpop import stashpop
    _dirty(git_repo)
    git_repo.runner.run("stash", "push", "-m", "pop me")
    cl = parse(["/command:stashpop", f"/path:{git_repo.root}"])
    assert stashpop(CommandContext(cl=cl)) == "ok"
    assert (Path(git_repo.root) / "a.txt").read_text() == "dirty\n"
    assert _stash_count(git_repo) == 0


def test_TC_STASH_007_drop(qapp, git_repo):
    """删除指定 stash（当前无 UI 入口，标记跳过）。"""
    pytest.skip("暂无 stash drop 的 UI 入口")


def test_TC_STASH_008_clear_from_reflog(qapp, ui, git_repo, monkeypatch):
    """reflog 的 Clear stash 按钮 → 清空所有 stash。"""
    from pytortoisegit.dialogs.reflogdlg import ReflogDlg
    _dirty(git_repo)
    git_repo.runner.run("stash", "push", "-m", "clear me")
    assert _stash_count(git_repo) == 1
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    dlg = ReflogDlg(git_repo)
    dlg.show()
    ui.click(dlg.btn_clearstash)
    assert _stash_count(git_repo) == 0
