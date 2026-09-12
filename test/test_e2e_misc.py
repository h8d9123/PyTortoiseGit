"""E2E：克隆/补丁/导出/工作树（TC-REPO / TC-PATCH / TC-WORKTREE）与不可测项。

运行：QT_QPA_PLATFORM=offscreen python -m pytest test/test_e2e_misc.py -v
"""

from pathlib import Path

import pytest
from PySide6.QtWidgets import QDialog


# ---- TC-REPO：克隆 ----

def test_TC_REPO_CLONE_001_local_bare(qapp, ui, remote_repo, tmp_path, auto_progress):
    """克隆本地 bare 仓库 → 目标目录生成工作区。"""
    from pytortoisegit.dialogs.clonedlg import CloneDlg
    target = tmp_path / "cloned"
    dlg = CloneDlg(url=str(remote_repo.bare))
    dlg.show()
    dlg.dir_edit.setText(str(target))
    ui.click(dlg.btn_ok)
    assert dlg.result() == QDialog.DialogCode.Accepted
    assert (target / "a.txt").exists()
    assert (target / ".git").exists()


def test_TC_REPO_CLONE_002_empty_url(qapp, ui, tmp_path):
    """URL 为空 → 不开始克隆。"""
    from pytortoisegit.dialogs.clonedlg import CloneDlg
    dlg = CloneDlg(url="")
    dlg.show()
    dlg.dir_edit.setText(str(tmp_path / "x"))
    ui.click(dlg.btn_ok)
    assert dlg.result() != QDialog.DialogCode.Accepted


# ---- TC-PATCH：导出/生成/应用 ----

def test_TC_PATCH_EXPORT_001(qapp, ui, git_repo, tmp_path, auto_progress):
    """导出到 zip → 文件生成。"""
    from pytortoisegit.dialogs.exportdlg import ExportDlg
    out = tmp_path / "export.zip"
    dlg = ExportDlg(git_repo)
    dlg.show()
    dlg.file_edit.setText(str(out))
    ui.click(dlg.btn_ok)
    assert dlg.result() == QDialog.DialogCode.Accepted
    assert out.exists() and out.stat().st_size > 0


def test_TC_PATCH_FORMATPATCH_001(qapp, ui, git_repo, tmp_path, auto_progress):
    """Format Patch → 生成 .patch 文件。"""
    from pytortoisegit.dialogs.formatpatchdlg import FormatPatchDlg
    (Path(git_repo.root) / "a.txt").write_text("changed\n", encoding="utf-8")
    git_repo.runner.run("add", "-A")
    git_repo.runner.run("commit", "-m", "patch me")
    dlg = FormatPatchDlg(git_repo)
    dlg.show()
    dlg.dir_combo.setCurrentText(str(tmp_path))
    dlg.rd_num.setChecked(True)
    dlg.num_edit.setValue(1)
    ui.click(dlg.btn_ok)
    assert dlg.result() == QDialog.DialogCode.Accepted
    assert list(tmp_path.glob("*.patch"))


def test_TC_PATCH_APPLYPATCH_001(qapp, ui, git_repo, tmp_path, auto_progress):
    """Apply Patch → 改动应用到工作区。"""
    (Path(git_repo.root) / "a.txt").write_text("patched\n", encoding="utf-8")
    patch = tmp_path / "p.diff"
    patch.write_text(git_repo.runner.run("diff").stdout, encoding="utf-8")
    git_repo.runner.run("checkout", "--", "a.txt")
    assert (Path(git_repo.root) / "a.txt").read_text() == "line1\nline2\nline3\n"
    from pytortoisegit.dialogs.applypatchdlg import ApplyPatchDlg
    dlg = ApplyPatchDlg(git_repo, patches=[str(patch)])
    dlg.show()
    ui.click(dlg.btn_apply)
    assert (Path(git_repo.root) / "a.txt").read_text() == "patched\n"


# ---- TC-WORKTREE ----

def test_TC_WORKTREE_001_list(qapp, ui, git_repo):
    """工作树列表 → 至少当前工作树。"""
    from pytortoisegit.dialogs.worktreelistdlg import WorktreeListDlg
    dlg = WorktreeListDlg(git_repo)
    dlg.show()
    assert dlg.tree.topLevelItemCount() >= 1


def test_TC_WORKTREE_002_create(qapp, ui, git_repo, tmp_path, auto_progress):
    """创建工作树 → 新目录生成。"""
    from pytortoisegit.dialogs.worktreecreatedlg import WorktreeCreateDlg
    wt = tmp_path / "wt"
    dlg = WorktreeCreateDlg(git_repo)
    dlg.show()
    dlg.dir_edit.setText(str(wt))
    ui.click(dlg.btn_ok)
    assert dlg.result() == QDialog.DialogCode.Accepted
    assert wt.exists()
    assert "wt" in git_repo.runner.run("worktree", "list").stdout


# ---- 环境相关，标记跳过 ----

@pytest.mark.skip(reason="需要可用的子模块远程仓库")
def test_TC_SUBMODULE_001_add():
    pass


@pytest.mark.skip(reason="需要 git-lfs 环境")
def test_TC_LFS_001_lock():
    pass


@pytest.mark.skip(reason="Shell 右键集成仅 Windows")
def test_TC_SHELL_001_install():
    pass
