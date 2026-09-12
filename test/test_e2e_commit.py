"""E2E：提交与工作区（TC-COMMIT / TC-ADD / TC-IGNORE / TC-REVERT / TC-RESET / TC-CLEAN）。

运行：QT_QPA_PLATFORM=offscreen python -m pytest test/test_e2e_commit.py -v
"""

from pathlib import Path

import pytest
from PySide6.QtWidgets import QDialog, QMessageBox


def _open_commit(qapp, ui, repo, require_rows=True):
    from pytortoisegit.dialogs.commitdlg import CommitDlg
    dlg = CommitDlg(repo)
    dlg.show()
    if require_rows:
        assert ui.wait_until(lambda: dlg.status_tree.topLevelItemCount() > 0), \
            "文件列表未加载"
    else:
        ui.wait(300)
    return dlg


def _no_warning(monkeypatch, method="warning"):
    monkeypatch.setattr(QMessageBox, method,
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok))


# ---- TC-COMMIT ----

def test_TC_COMMIT_001_commit_modified_file(qapp, ui, git_repo):
    """已修改文件勾选+信息+提交 → 新提交且工作区干净。"""
    (Path(git_repo.root) / "a.txt").write_text("line1\nchanged\nline3\n", encoding="utf-8")
    dlg = _open_commit(qapp, ui, git_repo)
    ui.set_text(dlg.message_edit, "e2e: commit modified file")
    dlg._toggle_check_group("All")
    assert dlg._checked_paths()
    ui.click(dlg.btn_commit)
    assert dlg.result() == QDialog.DialogCode.Accepted
    assert git_repo.runner.run("log", "-1", "--format=%s").stdout.strip() == \
        "e2e: commit modified file"
    assert git_repo.runner.run("status", "--porcelain").stdout.strip() == ""


def test_TC_COMMIT_002_commit_untracked_file(qapp, ui, git_repo):
    """未跟踪文件勾选后提交 → 文件入库。"""
    (Path(git_repo.root) / "new.txt").write_text("new\n", encoding="utf-8")
    dlg = _open_commit(qapp, ui, git_repo)
    ui.set_text(dlg.message_edit, "e2e: add new file")
    dlg._toggle_check_group("All")
    ui.click(dlg.btn_commit)
    assert dlg.result() == QDialog.DialogCode.Accepted
    files = git_repo.runner.run("ls-files").stdout
    assert "new.txt" in files
    assert git_repo.runner.run("status", "--porcelain").stdout.strip() == ""


def test_TC_COMMIT_003_select_all_none(qapp, ui, git_repo):
    """全选/全不选链接切换勾选状态与统计。"""
    from PySide6.QtCore import Qt
    (Path(git_repo.root) / "a.txt").write_text("x\n", encoding="utf-8")
    (Path(git_repo.root) / "new.txt").write_text("y\n", encoding="utf-8")
    dlg = _open_commit(qapp, ui, git_repo)
    dlg._toggle_check_group("All")
    total = dlg.status_tree.topLevelItemCount()
    checked = sum(1 for i in range(total)
                  if dlg.status_tree.topLevelItem(i).checkState(0) == Qt.CheckState.Checked)
    assert checked == total
    dlg._toggle_check_group("None")
    checked = sum(1 for i in range(total)
                  if dlg.status_tree.topLevelItem(i).checkState(0) == Qt.CheckState.Checked)
    assert checked == 0


def test_TC_COMMIT_004_empty_message_validation(qapp, ui, git_repo, monkeypatch):
    """空提交信息 → 提示且不关闭、不产生提交。"""
    (Path(git_repo.root) / "a.txt").write_text("changed\n", encoding="utf-8")
    _no_warning(monkeypatch)
    dlg = _open_commit(qapp, ui, git_repo)
    dlg._toggle_check_group("All")
    dlg.message_edit.setPlainText("")
    ui.click(dlg.btn_commit)
    assert dlg.result() != QDialog.DialogCode.Accepted
    assert git_repo.runner.run("log", "-1", "--format=%s").stdout.strip() == "initial"


def test_TC_COMMIT_005_no_file_validation(qapp, ui, git_repo, monkeypatch):
    """未勾选文件 → 提示且不提交。"""
    (Path(git_repo.root) / "a.txt").write_text("changed\n", encoding="utf-8")
    _no_warning(monkeypatch)
    dlg = _open_commit(qapp, ui, git_repo)
    dlg._toggle_check_group("None")
    ui.set_text(dlg.message_edit, "msg")
    ui.click(dlg.btn_commit)
    assert dlg.result() != QDialog.DialogCode.Accepted
    assert git_repo.runner.run("log", "-1", "--format=%s").stdout.strip() == "initial"


def test_TC_COMMIT_006_new_branch_commit(qapp, ui, git_repo):
    """新分支提交 → 创建并切换分支后提交。"""
    (Path(git_repo.root) / "a.txt").write_text("changed\n", encoding="utf-8")
    dlg = _open_commit(qapp, ui, git_repo)
    ui.set_text(dlg.message_edit, "e2e: on new branch")
    dlg._toggle_check_group("All")
    dlg.chk_new_branch.setChecked(True)
    ui.set_text(dlg.newbranch_edit, "feature-commit")
    ui.click(dlg.btn_commit)
    assert dlg.result() == QDialog.DialogCode.Accepted
    assert git_repo.runner.run("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == \
        "feature-commit"


def test_TC_COMMIT_008_amend(qapp, ui, git_repo):
    """Amend → 提交数不变，信息更新。"""
    (Path(git_repo.root) / "a.txt").write_text("changed\n", encoding="utf-8")
    dlg = _open_commit(qapp, ui, git_repo)
    dlg._toggle_check_group("All")
    dlg.amend_box.setChecked(True)
    ui.set_text(dlg.message_edit, "amended subject")
    ui.click(dlg.btn_commit)
    assert dlg.result() == QDialog.DialogCode.Accepted
    assert git_repo.runner.run("rev-list", "--count", "HEAD").stdout.strip() == "1"
    assert git_repo.runner.run("log", "-1", "--format=%s").stdout.strip() == "amended subject"


def test_TC_COMMIT_009_message_only(qapp, ui, git_repo):
    """Message only → 允许空提交。"""
    dlg = _open_commit(qapp, ui, git_repo, require_rows=False)
    dlg.chk_message_only.setChecked(True)
    ui.set_text(dlg.message_edit, "empty commit")
    ui.click(dlg.btn_commit)
    assert dlg.result() == QDialog.DialogCode.Accepted
    assert git_repo.runner.run("log", "-1", "--format=%s").stdout.strip() == "empty commit"


def test_TC_COMMIT_011_signoff(qapp, ui, git_repo):
    """Signed-off-by 按钮追加签名行。"""
    dlg = _open_commit(qapp, ui, git_repo, require_rows=False)
    ui.click(dlg.signoff_btn)
    assert "Signed-off-by: E2E Tester <e2e@example.com>" in dlg.message_edit.toPlainText()


def test_TC_COMMIT_012_set_author(qapp, ui, git_repo):
    """设置作者 → 提交作者为指定值。"""
    (Path(git_repo.root) / "a.txt").write_text("changed\n", encoding="utf-8")
    dlg = _open_commit(qapp, ui, git_repo)
    dlg._toggle_check_group("All")
    ui.set_text(dlg.message_edit, "by other author")
    dlg.chk_set_author.setChecked(True)
    ui.set_text(dlg.author_edit, "Other Author <other@example.com>")
    ui.click(dlg.btn_commit)
    assert dlg.result() == QDialog.DialogCode.Accepted
    assert "Other Author" in git_repo.runner.run("log", "-1", "--format=%an").stdout


def test_TC_COMMIT_013_text_info_updates(qapp, ui, git_repo):
    """消息框输入后字词统计实时更新。"""
    dlg = _open_commit(qapp, ui, git_repo, require_rows=False)
    ui.set_text(dlg.message_edit, "line one\nline two")
    assert dlg.text_info.text() != ""
    assert "2" in dlg.text_info.text()  # 2 lines


def test_TC_COMMIT_015_refresh_f5(qapp, ui, git_repo):
    """F5 刷新文件列表，出现外部新增改动。"""
    dlg = _open_commit(qapp, ui, git_repo, require_rows=False)
    (Path(git_repo.root) / "later.txt").write_text("later\n", encoding="utf-8")
    from PySide6.QtCore import Qt
    ui.key(dlg, Qt.Key.Key_F5)
    assert ui.wait_until(lambda: any(
        dlg.status_tree.topLevelItem(i).text(0).endswith("later.txt")
        for i in range(dlg.status_tree.topLevelItemCount())))


# ---- TC-ADD ----

def test_TC_ADD_001_add_untracked(qapp, ui, git_repo, auto_progress):
    """Add 勾选未跟踪文件 → 进入暂存区。"""
    from pytortoisegit.dialogs.adddlg import AddDlg
    (Path(git_repo.root) / "new.txt").write_text("new\n", encoding="utf-8")
    dlg = AddDlg(git_repo)
    dlg.show()
    ui.click(dlg.btn_ok)
    assert dlg.result() == QDialog.DialogCode.Accepted
    assert "new.txt" in git_repo.runner.run("diff", "--cached", "--name-only").stdout


# ---- TC-IGNORE / TC-UNIGNORE ----

def test_TC_IGNORE_001_add_to_gitignore(qapp, ui, git_repo):
    """添加到 .gitignore → 文件被忽略。"""
    from pytortoisegit.dialogs.ignoredlg import IgnoreDlg
    target = Path(git_repo.root) / "secret.txt"
    target.write_text("x\n", encoding="utf-8")
    dlg = IgnoreDlg(git_repo, paths=[str(target)])
    dlg.show()
    ui.click(dlg.btn_ok)
    assert dlg.result() == QDialog.DialogCode.Accepted
    assert "secret.txt" in (Path(git_repo.root) / ".gitignore").read_text()
    assert git_repo.runner.run("check-ignore", "-q", "secret.txt").returncode == 0


def test_TC_UNIGNORE_001_remove_from_gitignore(qapp, git_repo, monkeypatch):
    """unignore → 规则移除，文件不再被忽略。"""
    from pytortoisegit.cmdline import parse
    from pytortoisegit.commands.dispatcher import CommandContext
    from pytortoisegit.commands.unignore import unignore
    (Path(git_repo.root) / ".gitignore").write_text("secret.txt\n", encoding="utf-8")
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok))
    cl = parse(["/command:unignore", f"/path:{git_repo.root}",
                f"/path:{Path(git_repo.root) / 'secret.txt'}"])
    assert unignore(CommandContext(cl=cl)) == "ok"
    assert "secret.txt" not in (Path(git_repo.root) / ".gitignore").read_text()


# ---- TC-REVERT ----

def test_TC_REVERT_001_revert_modified(qapp, ui, git_repo, auto_progress):
    """还原已修改文件 → 内容回到 HEAD。"""
    from pytortoisegit.dialogs.revertdlg import RevertDlg
    f = Path(git_repo.root) / "a.txt"
    f.write_text("line1\nchanged\nline3\n", encoding="utf-8")
    dlg = RevertDlg(git_repo)
    dlg.show()
    ui.click(dlg.btn_ok)
    assert dlg.result() == QDialog.DialogCode.Accepted
    assert f.read_text() == "line1\nline2\nline3\n"


def test_TC_REVERT_002_revert_deleted(qapp, ui, git_repo, auto_progress):
    """还原已删除文件 → 文件恢复。"""
    from pytortoisegit.dialogs.revertdlg import RevertDlg
    f = Path(git_repo.root) / "a.txt"
    f.unlink()
    dlg = RevertDlg(git_repo)
    dlg.show()
    ui.click(dlg.btn_ok)
    assert dlg.result() == QDialog.DialogCode.Accepted
    assert f.exists()


# ---- TC-RESET ----

def _second_commit(repo):
    (Path(repo.root) / "a.txt").write_text("second\n", encoding="utf-8")
    repo.runner.run("add", "-A")
    repo.runner.run("commit", "-m", "second")
    first = repo.runner.run("rev-parse", "HEAD~1").stdout.strip()
    return first


def test_TC_RESET_001_mixed(qapp, ui, git_repo, auto_progress):
    """Reset mixed → HEAD 回退，工作区改动保留。"""
    from pytortoisegit.dialogs.resetdlg import ResetDlg
    first = _second_commit(git_repo)
    dlg = ResetDlg(git_repo, commit=first)
    dlg.rd_mixed.setChecked(True)
    dlg.show()
    ui.click(dlg.btn_ok)
    assert git_repo.runner.run("rev-parse", "HEAD").stdout.strip() == first
    # 工作区文件保留为 second 内容
    assert (Path(git_repo.root) / "a.txt").read_text() == "second\n"


def test_TC_RESET_002_hard(qapp, ui, git_repo, auto_progress):
    """Reset hard → HEAD 与工作区都回退。"""
    from pytortoisegit.dialogs.resetdlg import ResetDlg
    first = _second_commit(git_repo)
    dlg = ResetDlg(git_repo, commit=first)
    dlg.rd_hard.setChecked(True)
    dlg.show()
    ui.click(dlg.btn_ok)
    assert git_repo.runner.run("rev-parse", "HEAD").stdout.strip() == first
    assert (Path(git_repo.root) / "a.txt").read_text() == "line1\nline2\nline3\n"


def test_TC_RESET_003_soft(qapp, ui, git_repo, auto_progress):
    """Reset soft → HEAD 回退，改动进入暂存区。"""
    from pytortoisegit.dialogs.resetdlg import ResetDlg
    first = _second_commit(git_repo)
    dlg = ResetDlg(git_repo, commit=first)
    dlg.rd_soft.setChecked(True)
    dlg.show()
    ui.click(dlg.btn_ok)
    assert git_repo.runner.run("rev-parse", "HEAD").stdout.strip() == first
    assert "a.txt" in git_repo.runner.run("diff", "--cached", "--name-only").stdout


# ---- TC-CLEAN ----

def test_TC_CLEAN_001_clean_untracked(qapp, ui, git_repo, auto_progress):
    """Clean → 未跟踪文件被删除。"""
    from pytortoisegit.dialogs.cleandlg import CleanDlg
    f = Path(git_repo.root) / "junk.txt"
    f.write_text("junk\n", encoding="utf-8")
    dlg = CleanDlg(git_repo)
    dlg.rd_no.setChecked(True)
    dlg.show()
    ui.click(dlg.btn_ok)
    assert not f.exists()


# ---- TC-REMOVE / TC-RENAME ----

def test_TC_REMOVE_001_remove_tracked(qapp, git_repo, monkeypatch):
    """Remove → 文件从索引与工作区删除。"""
    from pytortoisegit.cmdline import parse
    from pytortoisegit.commands.dispatcher import CommandContext
    from pytortoisegit.commands.remove import remove
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    cl = parse(["/command:remove", f"/path:{Path(git_repo.root) / 'a.txt'}"])
    assert remove(CommandContext(cl=cl)) == "ok"
    assert not (Path(git_repo.root) / "a.txt").exists()


def test_TC_RENAME_001_rename_file(qapp, ui, git_repo, auto_progress):
    """Rename → git 记录重命名。"""
    from pytortoisegit.dialogs.renamedlg import RenameDlg
    dlg = RenameDlg(git_repo, paths=["a.txt"])
    ui.set_text(dlg.name_edit, "b.txt")
    dlg.show()
    ui.click(dlg.btn_ok)
    assert dlg.result() == QDialog.DialogCode.Accepted
    assert (Path(git_repo.root) / "b.txt").exists()
    status = git_repo.runner.run("status", "--porcelain").stdout
    assert "b.txt" in status
