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


def test_finddlg_layout(qapp):
    """对齐 IDD_FIND：复选框一行一个；按钮同一列。"""
    from pytortoisegit.merge.finddlg import FindDlg
    dlg = FindDlg()
    dlg.resize(500, 220)
    dlg.show()
    qapp.processEvents()
    chks = [dlg.chk_case, dlg.chk_limit, dlg.chk_up, dlg.chk_whole]
    ys = [c.y() for c in chks]
    assert len(set(ys)) == 4 and ys == sorted(ys)  # 一行一个，纵向递增
    btns = [dlg._btn_find, dlg._btn_replace, dlg._btn_replace_all,
            dlg._btn_count, dlg._btn_cancel]
    xs = [b.x() for b in btns]
    bys = [b.y() for b in btns]
    assert len(set(xs)) == 1                      # 同一列
    assert len(set(bys)) == 5 and bys == sorted(bys)
    # 复选框在左列、按钮在右列
    assert max(c.x() for c in chks) < min(b.x() for b in btns)
    dlg.reject()


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


def test_apputils_helpers(qapp):
    from pytortoisegit.merge.apputils import intense_color, has_clipboard_format
    from PySide6.QtGui import QColor
    # scale 0 → 颜色不变
    assert intense_color(0, QColor(200, 200, 200)) == QColor(200, 200, 200)
    # 浅色变暗
    darker = intense_color(255, QColor(200, 200, 200))
    assert darker.red() < 200
    assert isinstance(has_clipboard_format("text/plain"), bool)


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


def test_xsplitter(qapp):
    from pytortoisegit.merge.xsplitter import XSplitter
    from PySide6.QtWidgets import QWidget
    sp = XSplitter()
    sp.addWidget(QWidget())
    sp.addWidget(QWidget())
    assert sp.count() == 2
    sp.lock_bar(True)
    assert sp.is_bar_locked()
    sp.hide_column(1)
    assert sp.is_column_hidden(1)
    sp.show_column(1)
    assert not sp.is_column_hidden(1)
    sp.center_splitter()


def test_editorconfig(tmp_path):
    from pytortoisegit.merge.editorconfigwrapper import EditorConfigWrapper
    from pytortoisegit.merge.eol import EOL
    from pytortoisegit.merge.filetextlines import UnicodeType
    (tmp_path / ".editorconfig").write_text(
        "root = true\n\n[*.txt]\nindent_style = space\nindent_size = 4\n"
        "end_of_line = crlf\ncharset = utf-8\n", encoding="utf-8")
    f = tmp_path / "a.txt"
    f.write_text("x", encoding="utf-8")
    w = EditorConfigWrapper()
    assert w.load(str(f))
    assert w.indent_style.get() is True
    assert w.indent_size.get() == 4
    assert w.end_of_line.get() == EOL.CRLF
    assert w.charset.get() == UnicodeType.UTF8
    # 扩展名不匹配 → 不应用
    f2 = tmp_path / "b.py"
    f2.write_text("x", encoding="utf-8")
    w2 = EditorConfigWrapper()
    w2.load(str(f2))
    assert w2.indent_size.is_null()
