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
