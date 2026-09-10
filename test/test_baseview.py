"""BaseView 空白/EOL/编码工具（对齐 CBaseView）。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from pytortoisegit.merge.baseview import BaseView
from pytortoisegit.merge.viewdata import DiffState, EOL, ViewData
from pytortoisegit.merge.filetextlines import UnicodeType


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _view(lines):
    v = BaseView()
    v.set_view_data([ViewData(t, DiffState.Normal, i + 1) for i, t in enumerate(lines)])
    return v


def test_convert_tab_to_spaces(qapp):
    v = _view(["\tfoo", "  \tbar", "baz"])
    v.tab_size = 4
    v.convert_tab_to_spaces()
    assert v.view_data[0].line == "    foo"
    # 2 空格 + tab：nPosOut=(2+4)-2%4=4 → 4 空格（对齐 C++ 算法）
    assert v.view_data[1].line == "    bar"
    assert v.view_data[2].line == "baz"


def test_remove_trail_white_chars(qapp):
    v = _view(["a  ", "b\t", "c"])
    v.remove_trail_white_chars()
    assert [vd.line for vd in v.view_data] == ["a", "b", "c"]


def test_tabularize(qapp):
    v = _view(["        foo", "baz"])
    v.tab_size = 4
    v.tabularize()
    assert v.view_data[0].line == "\t\tfoo"
    assert v.view_data[1].line == "baz"


def test_whitechars_properties(qapp):
    v = _view(["\ta", "b  ", "c"])
    v.view_data[0].ending = EOL.CRLF
    v.view_data[1].ending = EOL.LF
    v.line_endings = EOL.CRLF
    props = v.get_whitechars_properties()
    assert props.has_trail_white_chars
    assert props.has_tabs_to_convert
    assert props.has_mixed_eols


def test_line_endings(qapp):
    v = _view(["a", "b"])
    v.line_endings = EOL.LF
    assert v.get_line_endings(has_mixed_eols=False) == EOL.LF
    v.line_endings = EOL.AutoLine
    assert v.get_line_endings(has_mixed_eols=False) == EOL.CRLF
    assert v.get_line_endings(has_mixed_eols=True) == EOL.AutoLine


def test_replace_line_endings(qapp):
    v = _view(["a", "b"])
    v.view_data[0].ending = EOL.CRLF
    v.view_data[1].ending = EOL.CRLF
    v.line_endings = EOL.CRLF
    v.replace_line_endings(EOL.LF)
    assert all(vd.ending == EOL.LF for vd in v.view_data)


def test_text_type(qapp):
    v = _view(["a"])
    assert v.get_text_type() == UnicodeType.AUTOTYPE
    v.set_text_type(UnicodeType.UTF8)
    assert v.get_text_type() == UnicodeType.UTF8
