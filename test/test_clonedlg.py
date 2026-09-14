"""CloneDlg 测试：Load Putty Key 置灰、From SVN 模式与 git svn clone 参数。"""

import pytest
from PySide6.QtWidgets import QDialog


@pytest.fixture(autouse=True)
def _english_ui():
    from pytortoisegit.res import strings
    strings.set_language("en")
    yield
    strings.set_language("zh")


def test_clone_putty_grayed_without_putty(qapp, monkeypatch):
    """非 PuTTY 客户端时 Load Putty Key 应灰掉（对齐 IsSSHPutty）。"""
    from pytortoisegit.dialogs.clonedlg import CloneDlg
    monkeypatch.setattr(CloneDlg, "_is_ssh_putty", lambda self: False)
    dlg = CloneDlg()
    assert not dlg.chk_putty.isEnabled()
    assert not dlg.chk_putty.isChecked()
    assert not dlg.putty_edit.isEnabled()
    assert not dlg.btn_putty.isEnabled()


def test_clone_putty_enabled_links_edit(qapp, monkeypatch):
    from pytortoisegit.dialogs.clonedlg import CloneDlg
    monkeypatch.setattr(CloneDlg, "_is_ssh_putty", lambda self: True)
    dlg = CloneDlg()
    assert dlg.chk_putty.isEnabled()
    assert not dlg.putty_edit.isEnabled()      # 未勾选 → 编辑框灰
    dlg.chk_putty.setChecked(True)
    assert dlg.putty_edit.isEnabled()
    assert dlg.btn_putty.isEnabled()


def test_clone_svn_toggle_disables_git_options(qapp):
    from pytortoisegit.dialogs.clonedlg import CloneDlg
    dlg = CloneDlg()
    dlg.chk_depth.setChecked(True)
    dlg.chk_recursive.setChecked(True)
    dlg.chk_svn.setChecked(True)
    for w in (dlg.chk_depth, dlg.depth_edit, dlg.chk_bare, dlg.chk_recursive,
              dlg.chk_branch, dlg.branch_edit, dlg.chk_nocheckout):
        assert not w.isEnabled()
    for w in (dlg.chk_depth, dlg.chk_bare, dlg.chk_recursive,
              dlg.chk_branch, dlg.chk_nocheckout):
        assert not w.isChecked()
    assert dlg.chk_svn_trunk.isEnabled()
    assert dlg.svn_trunk_edit.text() == "trunk"
    dlg.chk_svn.setChecked(False)
    assert dlg.chk_depth.isEnabled()


def test_clone_svn_args(qapp):
    from pytortoisegit.dialogs.clonedlg import CloneDlg
    dlg = CloneDlg()
    dlg.chk_svn.setChecked(True)
    dlg.chk_origin.setChecked(True)
    dlg.origin_edit.setText("origin")
    dlg.chk_svn_trunk.setChecked(True)
    dlg.chk_svn_branch.setChecked(True)
    dlg.chk_svn_tag.setChecked(True)
    dlg.chk_svn_from.setChecked(True)
    dlg.svn_from_edit.setText("5")
    dlg.chk_username.setChecked(True)
    dlg.username_edit.setText("bob")
    args = dlg._build_svn_clone_args("svn://x/repo", "C:/dst")
    assert args[:2] == ["svn", "clone"]
    assert "--prefix" in args and "origin/" in args
    assert "-T" in args and "trunk" in args
    assert "-b" in args and "branches" in args
    assert "-t" in args and "tags" in args
    assert "-r" in args and "5:HEAD" in args
    assert "--username" in args and "bob" in args
    assert args[-2:] == ["svn://x/repo", "C:/dst"]


def test_clone_accept_uses_svn_args(qapp, monkeypatch, auto_progress):
    from pytortoisegit.dialogs import clonedlg
    captured = {}

    def fake_reporter(dlg, url, target, args):
        captured["args"] = args
        return True

    monkeypatch.setattr(clonedlg, "_clone_reporter", fake_reporter)
    dlg = clonedlg.CloneDlg()
    dlg.url_combo.setEditText("svn://x/repo")
    dlg.dir_edit.setText("C:/dst")
    dlg.chk_svn.setChecked(True)
    dlg._on_accept()
    assert captured["args"][:2] == ["svn", "clone"]
    assert dlg.result() == QDialog.DialogCode.Accepted


def test_clone_accept_uses_git_args(qapp, monkeypatch, auto_progress):
    from pytortoisegit.dialogs import clonedlg
    captured = {}

    def fake_reporter(dlg, url, target, args):
        captured["args"] = args
        return True

    monkeypatch.setattr(clonedlg, "_clone_reporter", fake_reporter)
    dlg = clonedlg.CloneDlg()
    dlg.url_combo.setEditText("https://x/y.git")
    dlg.dir_edit.setText("C:/dst")
    dlg.chk_depth.setChecked(True)
    dlg.chk_origin.setChecked(True)
    dlg._on_accept()
    assert captured["args"][0] == "clone"
    assert "--depth" in captured["args"]
    assert "--origin" in captured["args"]
