"""E2E：引用日志 Reflog（TC-REFLOG）。

运行：QT_QPA_PLATFORM=offscreen python -m pytest test/test_e2e_reflog.py -v
"""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QMenu


def _reflog(ui, repo):
    from pytortoisegit.dialogs.reflogdlg import ReflogDlg
    dlg = ReflogDlg(repo)
    dlg.show()
    assert ui.wait_until(lambda: dlg.table.rowCount() > 0)
    return dlg


def _two_commits(repo):
    (Path(repo.root) / "a.txt").write_text("second\n", encoding="utf-8")
    repo.runner.run("add", "-A")
    repo.runner.run("commit", "-m", "second")
    return repo.runner.run("rev-parse", "HEAD").stdout.strip()


def _choose_menu(monkeypatch, index):
    """用假 QMenu 替换右键菜单，模拟用户点选第 index 个菜单项。"""
    import pytortoisegit.dialogs.reflogdlg as mod

    class FakeMenu:
        def __init__(self, *a, **k):
            self._actions = []

        def addAction(self, *a, **k):
            act = object()
            self._actions.append(act)
            return act

        def exec(self, *a, **k):
            return self._actions[index]

    monkeypatch.setattr(mod, "QMenu", FakeMenu)


def test_TC_REFLOG_001_load(qapp, ui, git_repo):
    """reflog 列表加载：选择器/哈希/日期/消息。"""
    dlg = _reflog(ui, git_repo)
    assert dlg.table.rowCount() >= 1
    assert dlg.table.item(0, 0).text().startswith("HEAD@{")
    assert dlg.table.item(0, 1).text()


def test_TC_REFLOG_002_search_hit(qapp, ui, git_repo):
    """搜索命中并定位。"""
    _two_commits(git_repo)
    dlg = _reflog(ui, git_repo)
    dlg._on_search()
    sd = dlg._search_dlg
    ui.set_text(sd.edit, "second")
    ui.click(sd.btn_next)
    assert sd.status.text() == ""
    assert dlg.table.currentRow() >= 0


def test_TC_REFLOG_003_search_not_found(qapp, ui, git_repo):
    """搜索未命中 → 提示未找到。"""
    dlg = _reflog(ui, git_repo)
    dlg._on_search()
    sd = dlg._search_dlg
    ui.set_text(sd.edit, "zzz-no-such-entry-zzz")
    ui.click(sd.btn_next)
    assert sd.status.text() != ""


def test_TC_REFLOG_004_search_dialog_on_top(qapp, ui, git_repo):
    """搜索对话框浮于 reflog 之上。"""
    dlg = _reflog(ui, git_repo)
    dlg._on_search()
    sd = dlg._search_dlg
    assert sd.windowFlags() & Qt.WindowType.Tool
    assert sd.isVisible()


def test_TC_REFLOG_005_match_case(qapp, ui, git_repo):
    """区分大小写搜索。"""
    _two_commits(git_repo)
    dlg = _reflog(ui, git_repo)
    dlg._on_search()
    sd = dlg._search_dlg
    sd.chk_case.setChecked(True)
    ui.set_text(sd.edit, "SECOND")
    ui.click(sd.btn_next)
    assert sd.status.text() != ""  # 大小写不符，找不到


def test_TC_REFLOG_006_ref_combo_reload(qapp, ui, git_repo):
    """切换 ref 下拉 → 重新加载。"""
    git_repo.runner.run("checkout", "-b", "feat")
    (Path(git_repo.root) / "b.txt").write_text("b\n", encoding="utf-8")
    git_repo.runner.run("add", "-A")
    git_repo.runner.run("commit", "-m", "feat commit")
    git_repo.runner.run("checkout", "main")
    dlg = _reflog(ui, git_repo)
    dlg.ref_combo.setCurrentText("feat")
    dlg.ref_combo.activated.emit(dlg.ref_combo.currentIndex())
    assert ui.wait_until(lambda: any(
        "feat commit" in (dlg.table.item(r, 3).text() if dlg.table.item(r, 3) else "")
        for r in range(dlg.table.rowCount())))


def test_TC_REFLOG_007_copy_hash(qapp, ui, git_repo, monkeypatch):
    """右键复制完整哈希。"""
    _two_commits(git_repo)
    dlg = _reflog(ui, git_repo)
    copied = {}
    from pytortoisegit.utils.clipboard import ClipboardHelper
    monkeypatch.setattr(ClipboardHelper, "copy_text",
                        lambda self, t: copied.__setitem__("t", t))
    dlg.table.selectRow(1)
    _choose_menu(monkeypatch, 0)  # Copy full hash
    dlg._on_menu(dlg.table.viewport().rect().center())
    assert copied["t"] == dlg.entries[1].hash_


def test_TC_REFLOG_008_checkout_commit(qapp, ui, git_repo, monkeypatch):
    """右键检出该提交。"""
    _two_commits(git_repo)
    dlg = _reflog(ui, git_repo)
    dlg.table.selectRow(1)
    target = dlg.entries[1].hash_
    _choose_menu(monkeypatch, 1)  # Checkout
    dlg._on_menu(dlg.table.viewport().rect().center())
    assert git_repo.runner.run("rev-parse", "HEAD").stdout.strip().startswith(target)


def test_TC_REFLOG_009_create_branch_here(qapp, ui, git_repo, monkeypatch):
    """右键在此创建分支。"""
    _two_commits(git_repo)
    dlg = _reflog(ui, git_repo)
    dlg.table.selectRow(1)

    from pytortoisegit.dialogs import createbranchdlg
    real_exec = createbranchdlg.CreateBranchDlg.exec

    def fake_exec(self):
        self.name_edit.setText("from-reflog")
        self._accept()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(createbranchdlg.CreateBranchDlg, "exec", fake_exec)
    _choose_menu(monkeypatch, 2)  # Create branch here
    dlg._on_menu(dlg.table.viewport().rect().center())
    assert "from-reflog" in git_repo.runner.run(
        "branch", "--format=%(refname:short)").stdout


def test_TC_REFLOG_010_compare(qapp, ui, git_repo, monkeypatch):
    """右键与此提交比较。"""
    _two_commits(git_repo)
    dlg = _reflog(ui, git_repo)
    dlg.table.selectRow(1)
    seen = {}
    import pytortoisegit.dialogs.reflogdlg as mod

    class FakeDiff:
        def __init__(self, repo, rev1=None, rev2=None, parent=None, **k):
            seen.update(rev1=rev1, rev2=rev2)

        def exec(self):
            return 0

    monkeypatch.setattr(mod, "DiffDlg", FakeDiff)
    _choose_menu(monkeypatch, 3)  # Compare with this commit
    dlg._on_menu(dlg.table.viewport().rect().center())
    assert seen.get("rev1")  # DiffDlg 被打开
