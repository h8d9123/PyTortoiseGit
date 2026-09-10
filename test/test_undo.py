"""Undo 撤销/重做/分组 与 TempFiles。"""

import os

from pytortoisegit.merge.undo import AllViewState, CUndo
from pytortoisegit.merge.viewdata import DiffState, ViewData


def test_undo_redo():
    u = CUndo()
    left = [ViewData("a", DiffState.Normal)]
    right = [ViewData("b", DiffState.Normal)]
    u.add_state(AllViewState().snapshot(left, right))
    left[0].line = "changed"
    assert u.can_undo()
    assert u.undo(left, right)
    assert left[0].line == "a"
    assert u.can_redo()
    assert u.redo(left, right)
    assert left[0].line == "changed"


def test_undo_grouping():
    u = CUndo()
    assert not u.is_grouping()
    u.begin_grouping()
    assert u.is_grouping()
    u.end_grouping()
    assert not u.is_grouping()


def test_mark_as_original_state():
    u = CUndo()
    u.mark_as_original_state(True, False, False)
    assert u._original_left == 1
    assert u._original_right == 0


def test_tempfiles(tmp_path):
    from pytortoisegit.merge.tempfile import TempFiles
    tf = TempFiles()
    p = tf.get_temp_file_path(remove_at_end=True, path="x.diff")
    assert os.path.exists(p)
    assert p.endswith(".diff")
    tf.add_file_to_remove(p)
    tf.cleanup()
    assert not os.path.exists(p)


def test_tempfiles_dir():
    from pytortoisegit.merge.tempfile import TempFiles
    tf = TempFiles()
    d = tf.get_temp_dir_path()
    assert os.path.isdir(d)
    tf.cleanup()
    assert not os.path.isdir(d)
