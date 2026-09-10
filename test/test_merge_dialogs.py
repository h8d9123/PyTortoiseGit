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
