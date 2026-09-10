"""Merge 对话框：OpenDlg 模式/剪贴板等。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_opendlg_mode_merge(qapp):
    from pytortoisegit.merge.opendlg import OpenDlg
    dlg = OpenDlg()
    dlg.base_edit.setText("base.txt")
    dlg.your_edit.setText("your.txt")
    dlg.accept()
    assert dlg.mode == "merge"
    assert dlg.base_file == "base.txt"
    assert not dlg.from_clipboard


def test_opendlg_mode_apply(qapp):
    from pytortoisegit.merge.opendlg import OpenDlg
    dlg = OpenDlg()
    dlg.diff_edit.setText("patch.diff")
    dlg.clip_check.setChecked(True)
    dlg.accept()
    assert dlg.mode == "apply"
    assert dlg.unified_diff_file == "patch.diff"
    assert dlg.from_clipboard


def test_finddlg(qapp):
    from pytortoisegit.merge.finddlg import FindDlg, FindType
    dlg = FindDlg(replace_mode=True)
    dlg.find_combo.setEditText("foo")
    dlg.chk_limit.setChecked(True)
    dlg.chk_case.setChecked(True)
    dlg._accept_find(FindType.Count)
    assert dlg.find_string == "foo"
    assert dlg.find_type == FindType.Count
    assert dlg.is_limit_to_diffs()
    assert dlg.match_case()
    assert dlg.find_next() is False


def test_finddlg_find_mode(qapp):
    from pytortoisegit.merge.finddlg import FindDlg, FindType
    dlg = FindDlg(replace_mode=False)
    dlg.find_combo.setEditText("bar")
    dlg._accept_find(FindType.Find)
    assert dlg.find_next() is True
    assert dlg.search_up() is False


def test_regexfiltersdlg(qapp):
    from pytortoisegit.merge.regexfiltersdlg import RegexFiltersDlg
    dlg = RegexFiltersDlg(filters=[("a", "x", "y"), ("b", "p", "q")])
    assert dlg.filters == [("a", "x", "y"), ("b", "p", "q")]
    # 列表有三列
    assert dlg.list.columnCount() == 3
    assert dlg.list.topLevelItemCount() == 2
    # 持久化接口可调用
    dlg.save_filters()


def test_gotolinedlg(qapp):
    from pytortoisegit.merge.gotolinedlg import GotoLineDlg
    dlg = GotoLineDlg(line_count=100)
    dlg.set_limits(1, 50)
    dlg.set_label("行号:")
    dlg.spin.setValue(7)
    assert dlg.get_line_number() == 7


_DIFF = """diff --git a/a.txt b/a.txt
--- a/a.txt
+++ b/a.txt
@@ -1 +1 @@
-x
+y
"""


def test_filepatchesdlg(qapp):
    from pytortoisegit.merge.filepatchesdlg import FilePatchesDlg
    from pytortoisegit.merge.patch import Patch
    p = Patch()
    p.parse_text(_DIFF)
    dlg = FilePatchesDlg()
    called = []
    assert dlg.init(p, lambda *a: called.append(a), "/tmp")
    assert dlg.has_files()
    assert dlg.tree.topLevelItemCount() == 1
    assert dlg.set_file_status_as_patched("a.txt")
    assert not dlg.set_file_status_as_patched("nope.txt")
    dlg.tree.setCurrentItem(dlg.tree.topLevelItem(0))
    dlg.patch_selected()
    assert called  # 回调被调用


def test_settings_dialog(qapp):
    from pytortoisegit.merge.settings import Settings
    dlg = Settings()
    assert dlg.tabs.count() == 2
    dlg.main_page.tab_size_spin.setValue(8)
    dlg.main_page.chk_ignore_eol.setChecked(True)
    dlg.main_page.chk_one_pane.setChecked(True)
    dlg._save_and_accept()
    opts = dlg.main_options
    assert opts["tab_size"] == 8
    assert opts["ignoreeol"] is True
    assert opts["one_pane"] is True


def test_mergefiles_command(qapp, tmp_path):
    """独立文件合并：/theirs /mine → MergeFrm 本地两栏（对齐 TortoiseMerge）。"""
    from pytortoisegit.cmdline import CommandLine
    from pytortoisegit.commands.dispatcher import CommandContext
    from pytortoisegit.merge.mergefrm import MergeFrm
    import pytortoisegit.commands.mergefiles as mf
    a = tmp_path / "theirs.txt"
    a.write_bytes(b"x\n")
    b = tmp_path / "mine.txt"
    b.write_bytes(b"y\n")
    cl = CommandLine(verb="mergefiles")
    cl.options["theirs"] = [str(a)]
    cl.options["mine"] = [str(b)]
    ctx = CommandContext(qapp=None, cl=cl)
    holder = {}
    orig = MergeFrm.exec
    MergeFrm.exec = lambda self: holder.setdefault("f", self)
    try:
        res = mf.mergefiles(ctx)
    finally:
        MergeFrm.exec = orig
    assert res == "ok"
    f = holder["f"]
    assert f._local_left == str(a)
    assert f._local_right == str(b)
    assert [vd.line for vd in f.left_view.view_data] == ["x"]
    assert [vd.line for vd in f.right_view.view_data] == ["y"]
