"""块操作与保存序列化：对齐 TortoiseGitMerge RightView/BottomView/SaveFile。"""

from pytortoisegit.merge.blocks import (
    first_conflict_index, resolve_state, serialize_view, use_both_blocks,
    use_both_left_first, use_both_right_first, use_resolved_block, use_view_block,
)
from pytortoisegit.merge.viewdata import DiffState, ViewData


def _lines(texts, states=None):
    states = states or [DiffState.Normal] * len(texts)
    return [ViewData(t, s, i + 1) for i, (t, s) in enumerate(zip(texts, states))]


def _text(data):
    return [vd.line for vd in data]


def test_resolve_state_conflict():
    assert resolve_state(DiffState.Conflict) == DiffState.ConflictsResolved
    assert resolve_state(DiffState.ConflictEmpty) == DiffState.ConflictResolvedEmpty
    assert resolve_state(DiffState.Normal) == DiffState.Normal


def test_use_view_block_overwrites_right():
    left = _lines(["A", "B"], [DiffState.Removed, DiffState.Normal])
    right = _lines(["X", "B"], [DiffState.Added, DiffState.Normal])
    use_view_block(right, left, 0, 0)
    assert right[0].line == "A"
    assert right[0].state == DiffState.Normal


def test_use_resolved_block_marks_conflict():
    left = _lines(["theirs"], [DiffState.Conflict])
    bottom = _lines(["????"], [DiffState.Conflict])
    use_resolved_block(bottom, left, 0, 0)
    assert bottom[0].line == "theirs"
    assert bottom[0].state == DiffState.ConflictsResolved


def test_use_both_left_first_inserts():
    left = _lines(["L1", "L2"], [DiffState.Removed, DiffState.Removed])
    right = _lines(["R1", "R2"], [DiffState.Added, DiffState.Added])
    use_both_left_first(right, left, 0, 1)
    assert _text(right) == ["L1", "L2", "R1", "R2"]
    assert right[0].state == DiffState.TheirsAdded
    assert right[2].state == DiffState.YoursAdded
    assert _text(left) == ["L1", "L2", "", ""]
    assert left[2].state == DiffState.Empty
    assert len(left) == len(right)


def test_use_both_right_first_inserts():
    left = _lines(["L1", "L2"], [DiffState.Removed, DiffState.Removed])
    right = _lines(["R1", "R2"], [DiffState.Added, DiffState.Added])
    use_both_right_first(right, left, 0, 1)
    assert _text(right) == ["R1", "R2", "L1", "L2"]
    assert right[0].state == DiffState.Added
    assert right[2].state == DiffState.TheirsAdded
    assert _text(left) == ["", "", "L1", "L2"]
    assert len(left) == len(right)


def test_use_both_blocks_bottom_keeps_both():
    left = _lines(["T1", "T2"], [DiffState.Conflict, DiffState.Conflict])
    right = _lines(["M1", "M2"], [DiffState.Conflict, DiffState.Conflict])
    bottom = _lines(["?", "?"], [DiffState.Conflict, DiffState.Conflict])
    use_both_blocks(bottom, left, right, 0, 1, left, right)
    assert _text(bottom) == ["T1", "T2", "M1", "M2"]
    assert all(vd.state == DiffState.ConflictsResolved for vd in bottom)
    assert len(left) == len(right) == 4
    assert len(bottom) == 4


def test_serialize_skips_empty_and_removed():
    dest = _lines(["keep", "", "gone", "tail"],
                  [DiffState.Normal, DiffState.Empty,
                   DiffState.Removed, DiffState.Normal])
    assert serialize_view(dest, dest, dest) == ["keep", "tail"]


def test_serialize_writes_conflict_markers():
    left = _lines(["theirs"], [DiffState.Conflict])
    right = _lines(["mine"], [DiffState.Conflict])
    bottom = _lines(["????"], [DiffState.Conflict])
    assert serialize_view(bottom, left, right) == [
        "<<<<<<< .mine", "mine", "=======", "theirs", ">>>>>>> .theirs"]


def test_undo_restores_inserted_lines():
    from pytortoisegit.merge.undo import AllViewState, CUndo
    left = _lines(["L1", "L2"], [DiffState.Removed, DiffState.Removed])
    right = _lines(["R1", "R2"], [DiffState.Added, DiffState.Added])
    stack = CUndo()
    stack.add_state(AllViewState().snapshot(left, right))
    use_both_left_first(right, left, 0, 1)
    assert len(right) == 4
    assert stack.undo(left, right)
    assert _text(right) == ["R1", "R2"]
    assert _text(left) == ["L1", "L2"]


def test_first_conflict_index():
    data = _lines(["a", "b"], [DiffState.Normal, DiffState.Conflict])
    assert first_conflict_index(data) == 1
    assert first_conflict_index(_lines(["a"], [DiffState.Normal])) == -1
