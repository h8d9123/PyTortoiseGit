"""E2E：合并/冲突/解决（TC-MERGE / TC-CONFLICT / TC-RESOLVE）。

运行：QT_QPA_PLATFORM=offscreen python -m pytest test/test_e2e_merge.py -v
"""

from pathlib import Path

from PySide6.QtWidgets import QDialog


def _feature_no_conflict(repo):
    """feature 新增文件，main 不动 → 可快进合并。"""
    repo.runner.run("checkout", "-b", "feature")
    (Path(repo.root) / "b.txt").write_text("feature\n", encoding="utf-8")
    repo.runner.run("add", "-A")
    repo.runner.run("commit", "-m", "feature add b")
    feat = repo.runner.run("rev-parse", "HEAD").stdout.strip()
    repo.runner.run("checkout", "main")
    return feat


def _feature_conflict(repo):
    """feature 与 main 改同一行 → 冲突。"""
    repo.runner.run("checkout", "-b", "feature")
    (Path(repo.root) / "a.txt").write_text("line1\nfeature\nline3\n", encoding="utf-8")
    repo.runner.run("add", "-A")
    repo.runner.run("commit", "-m", "feature change")
    repo.runner.run("checkout", "main")
    (Path(repo.root) / "a.txt").write_text("line1\nmain\nline3\n", encoding="utf-8")
    repo.runner.run("add", "-A")
    repo.runner.run("commit", "-m", "main change")


def _merge_dlg(ui, repo, branch="feature"):
    from pytortoisegit.dialogs.mergedlg import MergeDlg
    dlg = MergeDlg(repo)
    dlg.show()
    idx = dlg.branch_combo.findText(branch)
    dlg.branch_combo.setCurrentIndex(max(0, idx))
    return dlg


def test_TC_MERGE_001_no_conflict(qapp, ui, git_repo, auto_progress):
    """无冲突合并 → 文件合并进来。"""
    _feature_no_conflict(git_repo)
    dlg = _merge_dlg(ui, git_repo)
    ui.click(dlg.btn_start)
    assert (Path(git_repo.root) / "b.txt").exists()


def test_TC_MERGE_002_fast_forward(qapp, ui, git_repo, auto_progress):
    """快进合并 → HEAD 前进到 feature。"""
    feat = _feature_no_conflict(git_repo)
    dlg = _merge_dlg(ui, git_repo)
    ui.click(dlg.btn_start)
    assert git_repo.runner.run("rev-parse", "HEAD").stdout.strip() == feat


def test_TC_MERGE_003_conflict(qapp, ui, git_repo, auto_progress):
    """冲突合并 → 产生冲突条目。"""
    _feature_conflict(git_repo)
    dlg = _merge_dlg(ui, git_repo)
    ui.click(dlg.btn_start)
    unmerged = git_repo.runner.run("ls-files", "-u").stdout
    assert "a.txt" in unmerged


def test_TC_MERGE_004_abort(qapp, ui, git_repo, auto_progress):
    """中止合并 → 回到合并前。"""
    _feature_conflict(git_repo)
    dlg = _merge_dlg(ui, git_repo)
    ui.click(dlg.btn_start)
    assert git_repo.runner.run("ls-files", "-u").stdout.strip() != ""
    dlg._on_abort()
    assert git_repo.runner.run("rev-parse", "--verify", "-q", "MERGE_HEAD").returncode != 0
    assert git_repo.runner.run("ls-files", "-u").stdout.strip() == ""


def test_TC_RESOLVE_001_single(qapp, ui, git_repo, auto_progress):
    """标记冲突文件已解决 → 文件进入暂存区。"""
    _feature_conflict(git_repo)
    git_repo.runner.run("merge", "feature")  # 直接制造冲突
    from pytortoisegit.dialogs.resolvedlg import ResolveDlg
    dlg = ResolveDlg(git_repo)
    dlg.show()
    assert dlg.resolve_list.topLevelItemCount() >= 1
    ui.click(dlg.btn_ok)
    assert dlg.result() == QDialog.DialogCode.Accepted
    assert "a.txt" in git_repo.runner.run("diff", "--cached", "--name-only").stdout


def test_TC_RESOLVE_002_all(qapp, ui, git_repo, auto_progress):
    """全部标记已解决。"""
    _feature_conflict(git_repo)
    git_repo.runner.run("merge", "feature")
    from pytortoisegit.dialogs.resolvedlg import ResolveDlg
    dlg = ResolveDlg(git_repo)
    dlg.show()
    dlg.chk_selectall.setChecked(True)
    ui.click(dlg.btn_ok)
    assert git_repo.runner.run("ls-files", "-u").stdout.strip() == ""
