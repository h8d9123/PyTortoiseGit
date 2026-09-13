"""低覆盖率对话框的测试。

覆盖 0%/低覆盖的对话框：LogOrderingDlg、HistoryDlg、RevGraphFilterDlg、
DeleteRemoteTagDlg、PatchViewDlg、ShellDlg。
"""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog


@pytest.fixture(autouse=True)
def _english_ui():
    from pytortoisegit.res import strings
    strings.set_language("en")
    yield
    strings.set_language("zh")


# ---------------------------------------------------------------------------
# LogOrderingDlg
# ---------------------------------------------------------------------------

def test_log_ordering_default_and_select(qapp):
    from pytortoisegit.dialogs.logorderingdlg import LogOrderingDlg
    dlg = LogOrderingDlg()
    assert dlg.combo.count() == 4
    assert dlg.selected == "default"
    dlg.combo.setCurrentIndex(0)
    dlg.btn_ok.click()
    assert dlg.selected == "topo-order"
    assert dlg.result() == QDialog.DialogCode.Accepted


def test_log_ordering_cancel(qapp):
    from pytortoisegit.dialogs.logorderingdlg import LogOrderingDlg
    dlg = LogOrderingDlg()
    dlg.btn_cancel.click()
    assert dlg.result() == QDialog.DialogCode.Rejected


# ---------------------------------------------------------------------------
# HistoryDlg
# ---------------------------------------------------------------------------

def test_history_entries_and_select(qapp):
    from pytortoisegit.dialogs.historydlg import HistoryDlg
    dlg = HistoryDlg(entries=["one", "two", "three"], title="History")
    assert dlg.list.count() == 3
    dlg.list.setCurrentRow(1)
    dlg.btn_ok.click()
    assert dlg.selected == "two"
    assert dlg.result() == QDialog.DialogCode.Accepted


def test_history_empty_accepts_none(qapp):
    from pytortoisegit.dialogs.historydlg import HistoryDlg
    dlg = HistoryDlg()
    assert dlg.list.count() == 0
    dlg._accept()
    assert dlg.selected is None


def test_history_double_click_accepts(qapp):
    from pytortoisegit.dialogs.historydlg import HistoryDlg
    dlg = HistoryDlg(entries=["x"])
    dlg.list.setCurrentRow(0)
    dlg.list.itemDoubleClicked.emit(dlg.list.item(0))
    assert dlg.selected == "x"


# ---------------------------------------------------------------------------
# RevGraphFilterDlg
# ---------------------------------------------------------------------------

def test_revgraph_filter_reset(qapp, git_repo):
    from pytortoisegit.dialogs.revgraphfilterdlg import RevGraphFilterDlg
    dlg = RevGraphFilterDlg(git_repo)
    dlg.from_edit.setText("HEAD~1")
    dlg.to_edit.setText("HEAD")
    dlg.chk_current.setChecked(True)
    dlg.chk_local.setChecked(True)
    dlg._reset()
    assert dlg.from_edit.text() == ""
    assert dlg.to_edit.text() == ""
    assert not dlg.chk_current.isChecked()
    assert not dlg.chk_local.isChecked()


def test_revgraph_filter_browse(qapp, git_repo, monkeypatch):
    from pytortoisegit.dialogs.revgraphfilterdlg import RevGraphFilterDlg

    class _FakeRefs:
        def __init__(self, *a, **k):
            pass

        def exec(self):
            return 1

        def _selected(self):
            return ("refs/heads/main", "main")

    monkeypatch.setattr("pytortoisegit.dialogs.browserefs.BrowseRefsDlg",
                        _FakeRefs)
    dlg = RevGraphFilterDlg(git_repo)
    dlg._browse_from()
    dlg._browse_to()
    assert dlg.from_edit.text() == "refs/heads/main"
    assert dlg.to_edit.text() == "refs/heads/main"


# ---------------------------------------------------------------------------
# DeleteRemoteTagDlg
# ---------------------------------------------------------------------------

def _remote_with_tag(remote_repo, tag="v1"):
    remote_repo.runner.run("tag", tag)
    remote_repo.runner.run("push", "origin", tag)


def test_delete_remote_tag_lists(qapp, remote_repo):
    from pytortoisegit.dialogs.deleteremotetagdlg import DeleteRemoteTagDlg
    _remote_with_tag(remote_repo)
    dlg = DeleteRemoteTagDlg(remote_repo.local, "origin")
    names = [dlg.tags_list.topLevelItem(i).text(0)
             for i in range(dlg.tags_list.topLevelItemCount())]
    assert "v1" in names


def test_delete_remote_tag_select_all_and_delete(qapp, remote_repo):
    from pytortoisegit.dialogs.deleteremotetagdlg import DeleteRemoteTagDlg
    _remote_with_tag(remote_repo)
    dlg = DeleteRemoteTagDlg(remote_repo.local, "origin")
    dlg._on_select_all(False)
    for i in range(dlg.tags_list.topLevelItemCount()):
        assert dlg.tags_list.topLevelItem(i).checkState(0) == Qt.CheckState.Unchecked
    dlg._on_select_all(True)
    dlg._on_delete()
    assert dlg.result() == QDialog.DialogCode.Accepted
    out = remote_repo.runner.run("ls-remote", "--tags", "origin").stdout
    assert "refs/tags/v1" not in out


def test_delete_remote_tag_context_menu(qapp, remote_repo, monkeypatch):
    from pytortoisegit.dialogs.deleteremotetagdlg import DeleteRemoteTagDlg
    copied = {}

    class _FakeClip:
        def copy_text(self, text):
            copied["text"] = text

    monkeypatch.setattr("pytortoisegit.utils.clipboard.ClipboardHelper",
                        _FakeClip)
    _remote_with_tag(remote_repo)
    dlg = DeleteRemoteTagDlg(remote_repo.local, "origin")
    _menu, acts = dlg._build_menu("v1")
    for act, key in acts.items():
        if key == "copy":
            dlg._handle_menu(key, "v1")
    assert copied["text"] == "v1"
    dlg._handle_menu("delete", "v1")        # 删除并移除列表项
    assert dlg.tags_list.topLevelItemCount() == 0


# ---------------------------------------------------------------------------
# ShellDlg
# ---------------------------------------------------------------------------

def test_shell_dlg_install_uninstall(qapp, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from pytortoisegit.dialogs import shelldlg
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: None))
    state = {"installed": False}
    monkeypatch.setattr(shelldlg, "status_text", lambda: "state")
    monkeypatch.setattr(shelldlg, "is_installed", lambda: state["installed"])
    monkeypatch.setattr(shelldlg, "install", lambda: 5)
    monkeypatch.setattr(shelldlg, "uninstall", lambda: 5)
    dlg = shelldlg.ShellDlg()
    dlg._refresh_state()
    assert dlg._status.text() == "state"
    # 未安装 → 安装
    dlg._do_install()
    # 已安装 → 再安装走 else 分支
    state["installed"] = True
    dlg._do_install()
    # 已安装 → 卸载
    state["installed"] = True
    dlg._do_uninstall()


# ---------------------------------------------------------------------------
# LfsLocksDlg
# ---------------------------------------------------------------------------

def test_lfs_locks_select_all_and_unlock(qapp, git_repo):
    from PySide6.QtWidgets import QTreeWidgetItem
    from pytortoisegit.dialogs.lfslocksdlg import LfsLocksDlg
    dlg = LfsLocksDlg(git_repo)
    for p in ("a.bin", "b.bin"):
        it = QTreeWidgetItem([p])
        it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        it.setCheckState(0, Qt.CheckState.Checked)
        dlg.lock_list.addTopLevelItem(it)
    dlg._on_select_all(False)
    assert all(dlg.lock_list.topLevelItem(i).checkState(0)
               == Qt.CheckState.Unchecked
               for i in range(dlg.lock_list.topLevelItemCount()))
    dlg._on_select_all(True)
    dlg.chk_force.setChecked(True)
    dlg._on_unlock()          # git-lfs 不可用也走完流程
    assert dlg.result() == QDialog.DialogCode.Accepted


def test_lfs_locks_context_menu(qapp, git_repo, monkeypatch):
    from PySide6.QtWidgets import QTreeWidgetItem
    from pytortoisegit.dialogs.lfslocksdlg import LfsLocksDlg
    copied = {}

    class _FakeClip:
        def copy_text(self, text):
            copied["text"] = text

    monkeypatch.setattr("pytortoisegit.utils.clipboard.ClipboardHelper",
                        _FakeClip)
    dlg = LfsLocksDlg(git_repo)
    dlg.lock_list.addTopLevelItem(QTreeWidgetItem(["a.bin"]))
    _menu, acts = dlg._build_menu("a.bin")
    assert "copy" in acts.values() and "unlock" in acts.values()
    dlg._handle_menu("copy", "a.bin")
    assert copied["text"] == "a.bin"
    dlg._handle_menu("unlock", "a.bin")
    assert dlg.result() == QDialog.DialogCode.Accepted


# ---------------------------------------------------------------------------
# SendMailDlg
# ---------------------------------------------------------------------------

def test_sendmail_dlg(qapp, git_repo):
    from pytortoisegit.dialogs.sendmaildlg import SendMailDlg
    dlg = SendMailDlg(git_repo, patches=["0001.patch", "0002.patch"])
    assert dlg.patch_list.topLevelItemCount() == 2
    dlg.to_edit.setText("a@b.com")
    dlg.chk_attach.setChecked(True)
    dlg.btn_send.click()
    assert dlg.result() == QDialog.DialogCode.Accepted


# ---------------------------------------------------------------------------
# PatchViewDlg
# ---------------------------------------------------------------------------

def test_patch_view_shows_text(qapp):
    from pytortoisegit.dialogs.patchviewdlg import PatchViewDlg
    dlg = PatchViewDlg("diff --git a/x b/x\n+line\n", title="x.txt")
    assert "diff --git" in dlg.view.toPlainText()
    assert dlg.windowTitle() == "x.txt"
