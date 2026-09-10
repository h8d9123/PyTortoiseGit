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


def test_normalize_revs_matches_git_diff_semantics():
    """修订号归一：单个修订视为基准 old，另一端为工作区。"""
    from pytortoisegit.merge.diffdata import normalize_revs
    assert normalize_revs("A", "B") == ("A", "B")
    # 只给一个（无论 rev1 还是 rev2）都作为基准 old
    assert normalize_revs("HEAD", None) == ("HEAD", None)
    assert normalize_revs(None, "HEAD") == ("HEAD", None)
    assert normalize_revs(None, None) == (None, None)


def test_diffdata_load_direction_not_reversed(tmp_path_factory):
    """回归：双击并排比较方向必须与 git diff 一致（old=修订，new=工作区）。"""
    from pytortoisegit.git.git import GitRunner
    from pytortoisegit.git.repo import Repository
    from pytortoisegit.merge.diffdata import DiffData
    parent = tmp_path_factory.mktemp("diffdir")
    root = parent / "repo"
    root.mkdir()
    runner = GitRunner(cwd=str(root))
    runner.init(str(root), initial_branch="main")
    runner.run("config", "user.email", "t@x.com")
    runner.run("config", "user.name", "T")
    (root / "a.txt").write_text("HEAD-line\n", encoding="utf-8")
    runner.run("add", "-A")
    runner.run("commit", "-m", "init")
    (root / "a.txt").write_text("WORKTREE-line\n", encoding="utf-8")
    repo = Repository.open(str(root))
    dd = DiffData(repo)

    # 等价于 git diff HEAD：old=HEAD, new=工作区
    left, right = dd.load("a.txt", None, "HEAD")
    assert [v.line for v in left] == ["HEAD-line"]
    assert [v.line for v in right] == ["WORKTREE-line"]
    # 只给 rev1 也应得到相同方向
    left2, right2 = dd.load("a.txt", "HEAD", None)
    assert [v.line for v in left2] == ["HEAD-line"]
    assert [v.line for v in right2] == ["WORKTREE-line"]


def test_ignore_comments_marks_filtered(tmp_path_factory):
    """忽略注释：仅注释不同的行标记为 FilteredDiff（对齐 DoTwoWayDiff）。"""
    import re
    from pytortoisegit.git.git import GitRunner
    from pytortoisegit.git.repo import Repository
    from pytortoisegit.merge.diffdata import DiffData, default_comment_tokens
    from pytortoisegit.merge.viewdata import DiffState
    root = tmp_path_factory.mktemp("dd_comments")
    runner = GitRunner(cwd=str(root))
    runner.init(str(root), initial_branch="main")
    runner.run("config", "user.email", "t@x.com")
    runner.run("config", "user.name", "T")
    (root / "a.py").write_bytes(b"x = 1  # old\nkeep\n")
    runner.run("add", "-A")
    runner.run("commit", "-m", "init")
    (root / "a.py").write_bytes(b"x = 1  # new\nkeep\n")
    repo = Repository.open(str(root))

    dd = DiffData(repo)
    dd.ignore_comments = True
    dd.set_comment_tokens(*default_comment_tokens("a.py"))
    left, right = dd.load("a.py", "HEAD", None)
    assert left[0].state == DiffState.FilteredDiff
    assert right[0].state == DiffState.FilteredDiff
    assert left[1].state == DiffState.Normal

    # 正则过滤（去掉 # 注释后相同）
    dd2 = DiffData(repo)
    dd2.set_regex_tokens(re.compile(r"#.*"), "")
    left2, right2 = dd2.load("a.py", "HEAD", None)
    assert left2[0].state == DiffState.FilteredDiff

    # 默认扩展名映射
    assert default_comment_tokens("x.cpp") == ("//", "/*", "*/")
    assert default_comment_tokens("x.html") == ("", "<!--", "-->")
    assert default_comment_tokens("x.py") == ("#", "", "")
