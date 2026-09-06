"""DiffData 行对齐：配对删除/新增，避免 hunk 间错位。"""

from pytortoisegit.merge.diffdata import align_lines, merge_three_views
from pytortoisegit.merge.inlinediff import inline_spans
from pytortoisegit.merge.viewdata import DiffState


def test_pair_changed_line_side_by_side():
    old = ["a", "b", "c"]
    new = ["a", "bX", "c"]
    patch = """diff --git a/f b/f
--- a/f
+++ b/f
@@ -2,1 +2,1 @@
-b
+bX
"""
    left, right = align_lines(old, new, patch, "f")
    assert [vd.line for vd in left] == ["a", "b", "c"]
    assert [vd.line for vd in right] == ["a", "bX", "c"]
    assert left[1].state == DiffState.Removed
    assert right[1].state == DiffState.Added
    assert left[1].linenumber == 2
    assert right[1].linenumber == 2


def test_pair_unequal_hunk_pads_empty():
    old = ["a", "b", "c"]
    new = ["a", "X", "Y", "c"]
    patch = """diff --git a/f b/f
--- a/f
+++ b/f
@@ -2,1 +2,2 @@
-b
+X
+Y
"""
    left, right = align_lines(old, new, patch, "f")
    assert [vd.line for vd in left] == ["a", "b", "", "c"]
    assert [vd.line for vd in right] == ["a", "X", "Y", "c"]
    assert left[1].state == DiffState.Removed
    assert right[1].state == DiffState.Added
    assert left[2].state == DiffState.Empty
    assert right[2].state == DiffState.Added


def test_two_hunks_do_not_drift():
    old = ["1", "2", "3", "4", "5", "6"]
    new = ["1", "2x", "2y", "3", "4", "5x", "6"]
    patch = """diff --git a/f b/f
--- a/f
+++ b/f
@@ -2,1 +2,2 @@
-2
+2x
+2y
@@ -5,1 +6,1 @@
-5
+5x
"""
    left, right = align_lines(old, new, patch, "f")
    assert [vd.line for vd in left] == ["1", "2", "", "3", "4", "5", "6"]
    assert [vd.line for vd in right] == ["1", "2x", "2y", "3", "4", "5x", "6"]
    assert left[5].line == "5" and left[5].state == DiffState.Removed
    assert right[5].line == "5x" and right[5].state == DiffState.Added
    assert left[3].state == DiffState.Normal and left[3].line == "3"


def test_align_without_patch_uses_difflib():
    old = ["keep", "old", "tail"]
    new = ["keep", "new", "tail"]
    left, right = align_lines(old, new, "")
    assert len(left) == len(right)
    changed = [(l.line, r.line) for l, r in zip(left, right)
               if l.state != DiffState.Normal or r.state != DiffState.Normal]
    assert ("old", "new") in changed or any(
        l.line == "old" and r.line == "new" for l, r in zip(left, right))


def test_three_way_same_grid():
    base = ["common", "x", "z"]
    theirs = ["common", "T", "z"]
    ours = ["common", "O", "z"]
    bt_l, th_r = align_lines(base, theirs, "")
    bo_l, ou_r = align_lines(base, ours, "")
    left, right, bottom = merge_three_views(bt_l, th_r, bo_l, ou_r)
    assert len(left) == len(right) == len(bottom)
    texts = [(l.line, r.line, b.line) for l, r, b in zip(left, right, bottom)]
    assert ("common", "common", "common") in texts
    assert any(l == "T" and r == "O" for l, r, _ in texts)


def test_change_plus_insert_keeps_unchanged_line():
    old = ["line1", "line2", "line3"]
    new = ["line1", "line2-changed", "line3", "extra"]
    left, right = align_lines(old, new, "")
    assert [vd.line for vd in left] == ["line1", "line2", "line3", ""]
    assert [vd.line for vd in right] == ["line1", "line2-changed", "line3", "extra"]
    assert left[2].state == DiffState.Normal
    assert right[2].state == DiffState.Normal


def test_inline_spans_char_and_word():
    lspans, rspans = inline_spans("hello world", "hello there", word_wise=True)
    assert lspans and rspans
    l2, r2 = inline_spans("abc", "axc", word_wise=False)
    assert l2 == [(1, 2)]
    assert r2 == [(1, 2)]
