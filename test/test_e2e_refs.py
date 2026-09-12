"""E2E：分支/标签/切换（TC-REF / TC-TAG / TC-BROWSE / TC-SWITCH）。

运行：QT_QPA_PLATFORM=offscreen python -m pytest test/test_e2e_refs.py -v
"""

from pathlib import Path

from PySide6.QtWidgets import QDialog, QInputDialog, QMessageBox


def _click_ok(dlg):
    dlg.btn_ok.click()


# ---- TC-REF：新建分支 ----

def test_TC_REF_001_create_and_switch(qapp, ui, git_repo):
    """创建并切换分支 → 分支存在且 HEAD 切换。"""
    from pytortoisegit.dialogs.createbranchdlg import CreateBranchDlg
    dlg = CreateBranchDlg(git_repo)
    ui.set_text(dlg.name_edit, "feature-a")
    dlg.show()
    _click_ok(dlg)
    assert dlg.result() == QDialog.DialogCode.Accepted
    assert "feature-a" in git_repo.runner.run("branch", "--format=%(refname:short)").stdout
    assert git_repo.runner.run("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == "feature-a"


def test_TC_REF_002_create_without_switch(qapp, ui, git_repo):
    """仅创建不切换 → 分支存在，HEAD 不变。"""
    from pytortoisegit.dialogs.createbranchdlg import CreateBranchDlg
    dlg = CreateBranchDlg(git_repo)
    ui.set_text(dlg.name_edit, "feature-b")
    dlg.switch_box.setChecked(False)
    dlg.show()
    _click_ok(dlg)
    assert dlg.result() == QDialog.DialogCode.Accepted
    assert "feature-b" in git_repo.runner.run("branch", "--format=%(refname:short)").stdout
    assert git_repo.runner.run("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == "main"


def test_TC_REF_003_empty_name_validation(qapp, ui, git_repo):
    """空分支名 → 不创建。"""
    from pytortoisegit.dialogs.createbranchdlg import CreateBranchDlg
    before = git_repo.runner.run("branch", "--format=%(refname:short)").stdout
    dlg = CreateBranchDlg(git_repo)
    dlg.show()
    _click_ok(dlg)
    assert dlg.result() != QDialog.DialogCode.Accepted
    assert git_repo.runner.run("branch", "--format=%(refname:short)").stdout == before


def test_TC_REF_004_duplicate_name(qapp, ui, git_repo, monkeypatch):
    """重名分支 → 提示失败，不覆盖。"""
    from pytortoisegit.dialogs.createbranchdlg import CreateBranchDlg
    git_repo.runner.run("branch", "dup")
    monkeypatch.setattr(QMessageBox, "warning",
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok))
    dlg = CreateBranchDlg(git_repo)
    ui.set_text(dlg.name_edit, "dup")
    dlg.show()
    _click_ok(dlg)
    assert dlg.result() != QDialog.DialogCode.Accepted


# ---- TC-TAG ----

def test_TC_TAG_001_lightweight(qapp, ui, git_repo):
    """轻量标签 → git tag 存在且为 commit 对象。"""
    from pytortoisegit.dialogs.createbranchdlg import CreateTagDlg
    dlg = CreateTagDlg(git_repo)
    ui.set_text(dlg.name_edit, "v0.1")
    dlg.show()
    _click_ok(dlg)
    assert dlg.result() == QDialog.DialogCode.Accepted
    assert "v0.1" in git_repo.runner.run("tag", "-l").stdout
    assert git_repo.runner.run("cat-file", "-t", "v0.1").stdout.strip() == "commit"


def test_TC_TAG_002_annotated(qapp, ui, git_repo):
    """附注标签 → tag 对象并含信息。"""
    from pytortoisegit.dialogs.createbranchdlg import CreateTagDlg
    dlg = CreateTagDlg(git_repo)
    ui.set_text(dlg.name_edit, "v0.2")
    dlg.annotated_box.setChecked(True)
    ui.set_text(dlg.msg_edit, "release v0.2")
    dlg.show()
    _click_ok(dlg)
    assert dlg.result() == QDialog.DialogCode.Accepted
    assert git_repo.runner.run("cat-file", "-t", "v0.2").stdout.strip() == "tag"
    assert "release v0.2" in git_repo.runner.run("tag", "-n", "-l", "v0.2").stdout


def test_TC_TAG_003_empty_name_validation(qapp, ui, git_repo):
    """空标签名 → 不创建。"""
    from pytortoisegit.dialogs.createbranchdlg import CreateTagDlg
    dlg = CreateTagDlg(git_repo)
    dlg.show()
    _click_ok(dlg)
    assert dlg.result() != QDialog.DialogCode.Accepted
    assert git_repo.runner.run("tag", "-l").stdout.strip() == ""


# ---- TC-BROWSE ----

def _browse(ui, repo):
    from pytortoisegit.dialogs.browserefs import BrowseRefsDlg
    dlg = BrowseRefsDlg(repo)
    dlg.show()
    assert ui.wait_until(lambda: dlg.tree.topLevelItemCount() > 0)
    return dlg


def _find_ref_item(dlg, name):
    for i in range(dlg.tree.topLevelItemCount()):
        top = dlg.tree.topLevelItem(i)
        for j in range(top.childCount()):
            child = top.child(j)
            if child.text(0) == name:
                return child
    return None


def test_TC_BROWSE_001_list_refs(qapp, ui, git_repo):
    """引用浏览 → 分组列出本地分支/标签/远程。"""
    git_repo.runner.run("branch", "b1")
    git_repo.runner.run("tag", "t1")
    dlg = _browse(ui, git_repo)
    labels = [dlg.tree.topLevelItem(i).text(0)
              for i in range(dlg.tree.topLevelItemCount())]
    assert any("Branches" in x or "分支" in x for x in labels)
    assert any("Tags" in x or "标签" in x for x in labels)
    assert _find_ref_item(dlg, "b1") is not None


def test_TC_BROWSE_002_delete_branch(qapp, ui, git_repo, monkeypatch):
    """删除本地分支 → 分支被删除。"""
    git_repo.runner.run("branch", "to-delete")
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    dlg = _browse(ui, git_repo)
    dlg.tree.setCurrentItem(_find_ref_item(dlg, "to-delete"))
    dlg._delete_selected()
    assert ui.wait_until(lambda: "to-delete" not in
                         git_repo.runner.run("branch", "--format=%(refname:short)").stdout)


def test_TC_BROWSE_003_delete_tag(qapp, ui, git_repo, monkeypatch):
    """删除标签 → 标签被删除。"""
    git_repo.runner.run("tag", "tag-to-delete")
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    dlg = _browse(ui, git_repo)
    dlg.tree.setCurrentItem(_find_ref_item(dlg, "tag-to-delete"))
    dlg._delete_selected()
    assert ui.wait_until(lambda: "tag-to-delete" not in git_repo.runner.run("tag", "-l").stdout)


# ---- TC-SWITCH ----

def test_TC_SWITCH_001_existing_branch(qapp, ui, git_repo, auto_progress):
    """切换到已存在分支 → HEAD 切换。"""
    from pytortoisegit.dialogs.gitswitchdlg import GitSwitchDlg
    git_repo.runner.run("branch", "feature-x")
    dlg = GitSwitchDlg(git_repo)
    ui.set_combo(dlg.branch_combo, "feature-x")
    ui.click(dlg.btn_ok)
    assert dlg.result() == QDialog.DialogCode.Accepted
    assert git_repo.runner.run("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == "feature-x"


def test_TC_SWITCH_002_nonexistent_stays_open(qapp, ui, git_repo, auto_progress):
    """切换不存在分支 → 失败保留，HEAD 不变。"""
    from pytortoisegit.dialogs.gitswitchdlg import GitSwitchDlg
    dlg = GitSwitchDlg(git_repo)
    ui.set_combo(dlg.branch_combo, "no-such-branch")
    ui.click(dlg.btn_ok)
    assert dlg.result() != QDialog.DialogCode.Accepted
    assert git_repo.runner.run("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == "main"


def test_TC_SWITCH_003_force(qapp, ui, git_repo, auto_progress):
    """强制切换覆盖本地改动。"""
    from pytortoisegit.dialogs.gitswitchdlg import GitSwitchDlg
    git_repo.runner.run("checkout", "-b", "other")
    (Path(git_repo.root) / "a.txt").write_text("other version\n", encoding="utf-8")
    git_repo.runner.run("add", "-A")
    git_repo.runner.run("commit", "-m", "other change")
    git_repo.runner.run("checkout", "main")
    (Path(git_repo.root) / "a.txt").write_text("local dirty\n", encoding="utf-8")
    dlg = GitSwitchDlg(git_repo)
    ui.set_combo(dlg.branch_combo, "other")
    dlg.chk_force.setChecked(True)
    ui.click(dlg.btn_ok)
    assert dlg.result() == QDialog.DialogCode.Accepted
    assert (Path(git_repo.root) / "a.txt").read_text() == "other version\n"


def test_TC_SWITCH_004_to_tag(qapp, ui, git_repo, auto_progress):
    """切换到标签 → detached HEAD。"""
    from pytortoisegit.dialogs.gitswitchdlg import GitSwitchDlg
    git_repo.runner.run("tag", "v9")
    dlg = GitSwitchDlg(git_repo)
    dlg.rd_tags.setChecked(True)
    ui.set_combo(dlg.tags_combo, "v9")
    ui.click(dlg.btn_ok)
    assert dlg.result() == QDialog.DialogCode.Accepted
    assert git_repo.runner.run("describe", "--tags").stdout.strip() == "v9"


def test_TC_SWITCH_005_to_commit(qapp, ui, git_repo, auto_progress):
    """切换到提交 → 检出指定提交。"""
    from pytortoisegit.dialogs.gitswitchdlg import GitSwitchDlg
    (Path(git_repo.root) / "a.txt").write_text("second\n", encoding="utf-8")
    git_repo.runner.run("add", "-A")
    git_repo.runner.run("commit", "-m", "second")
    first = git_repo.runner.run("rev-parse", "HEAD~1").stdout.strip()
    dlg = GitSwitchDlg(git_repo)
    dlg.rd_version.setChecked(True)
    dlg.version_combo.setCurrentText(first)
    ui.click(dlg.btn_ok)
    assert dlg.result() == QDialog.DialogCode.Accepted
    assert git_repo.runner.run("rev-parse", "HEAD").stdout.strip() == first


def test_TC_SWITCH_006_create_new_branch(qapp, ui, git_repo, auto_progress):
    """切换时新建分支并切换。"""
    from pytortoisegit.dialogs.gitswitchdlg import GitSwitchDlg
    dlg = GitSwitchDlg(git_repo)
    dlg.chk_newbranch.setChecked(True)
    ui.set_text(dlg.newbranch_edit, "brand-new")
    ui.click(dlg.btn_ok)
    assert dlg.result() == QDialog.DialogCode.Accepted
    assert git_repo.runner.run("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == "brand-new"


def test_TC_SWITCH_007_browse_ref_button(qapp, ui, git_repo, monkeypatch):
    """浏览引用按钮 → 回填所选引用。"""
    from pytortoisegit.dialogs.gitswitchdlg import GitSwitchDlg
    git_repo.runner.run("branch", "picked")
    dlg = GitSwitchDlg(git_repo)
    # 模拟用户在引用选择框中选中 picked
    monkeypatch.setattr(QInputDialog, "getItem",
                        staticmethod(lambda *a, **k: ("branch: picked", True)))
    ui.click(dlg.btn_browse_ref)
    assert dlg.branch_combo.currentText() == "picked"


def test_TC_SWITCH_008_branch_combo_lists(qapp, ui, git_repo):
    """分支下拉列出本地分支。"""
    from pytortoisegit.dialogs.gitswitchdlg import GitSwitchDlg
    git_repo.runner.run("branch", "listed")
    dlg = GitSwitchDlg(git_repo)
    items = [dlg.branch_combo.itemText(i) for i in range(dlg.branch_combo.count())]
    assert "main" in items and "listed" in items
