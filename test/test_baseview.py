"""BaseView 空白/EOL/编码工具（对齐 CBaseView）。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from pytortoisegit.merge.baseview import BaseView
from pytortoisegit.merge.viewdata import DiffState, EOL, HideState, ViewData
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


def test_state_classification(qapp):
    from pytortoisegit.merge.baseview import BaseView
    assert BaseView.is_state_conflicted(DiffState.Conflict)
    assert BaseView.is_state_conflicted(DiffState.ConflictAdded)
    assert not BaseView.is_state_conflicted(DiffState.Normal)
    assert BaseView.is_state_empty(DiffState.Empty)
    assert BaseView.is_state_empty(DiffState.Unknown)
    assert BaseView.is_state_removed(DiffState.Removed)
    assert BaseView.is_state_removed(DiffState.TheirsRemoved)
    assert BaseView.resolve_state(DiffState.Conflict) == DiffState.ConflictsResolved
    assert BaseView.resolve_state(DiffState.ConflictEmpty) == DiffState.ConflictResolvedEmpty
    assert BaseView.resolve_state(DiffState.Normal) == DiffState.Normal


def test_char_group(qapp):
    from pytortoisegit.merge.baseview import CharGroup
    v = _view(["a"])
    assert v.get_char_group(" ") == CharGroup.WHITESPACE
    assert v.get_char_group("\t") == CharGroup.WHITESPACE
    assert v.get_char_group("\x01") == CharGroup.CONTROL
    assert v.get_char_group("(") == CharGroup.WORDSEPARATOR
    assert v.get_char_group("a") == CharGroup.WORDLETTER
    assert v.is_word_separator(" ")
    assert v.is_word_separator("(")
    assert not v.is_word_separator("a")


def test_clean_empty_lines(qapp):
    a = _view(["a", "", "b"])
    b = _view(["x", "", "y"])
    a.view_data[1].state = DiffState.Empty
    b.view_data[1].state = DiffState.Empty
    assert a.clean_empty_lines([a, b]) == 1
    assert [vd.line for vd in a.view_data] == ["a", "b"]
    assert [vd.line for vd in b.view_data] == ["x", "y"]


def test_indentation(qapp):
    v = _view(["foo", "bar", "baz"])
    v.tab_size = 4
    v.add_indentation_for_selected_block(0, 1)
    assert v.view_data[0].line == "\tfoo"
    assert v.view_data[1].line == "\tbar"
    assert v.view_data[2].line == "baz"
    v.remove_indentation_for_selected_block(0, 1)
    assert v.view_data[0].line == "foo"
    assert v.view_data[1].line == "bar"


def test_line_length_with_tabs(qapp):
    v = _view(["a\tb"])
    v.tab_size = 4
    # 3 字符 + 1 tab → 3 + 1*(4-1) = 6
    assert v.get_line_length_with_tabs_converted(0) == 6
    assert v.get_view_line_length(0) == 3


def test_marked_word_array(qapp):
    v = _view(["foo bar foo", "foobar", "foo"])
    v.set_marked_word("foo")
    # 仅整词匹配：第 1、3 行命中，第 2 行("foobar")不命中
    assert v.marked_word_lines == [1, 0, 1]
    assert v.marked_word_count == 2


def test_find_string_array(qapp):
    v = _view(["test test", "no"])
    v.view_data[0].state = DiffState.Removed
    v.view_data[1].state = DiffState.Normal
    v.find_text = "test"
    v.limit_to_diff = True
    v.build_find_string_array()
    assert v.find_string_lines == [2, 0]  # Normal 行被 limit_to_diff 排除
    v.limit_to_diff = False
    v.build_find_string_array()
    assert v.find_string_lines[0] == 2


def test_is_view_line_hidden(qapp):
    v = _view(["a", "b"])
    v.view_data[1].hidestate = HideState.Hidden
    v.collapsed = False
    assert not v.is_view_line_hidden(1)
    v.collapsed = True
    assert v.is_view_line_hidden(1)
    assert not v.is_view_line_hidden(0)
