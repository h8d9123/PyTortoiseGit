"""MergeFrm 视图渲染：差异行背景色不得“渗透”到相邻行，相同行不得被当作移动块。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from pytortoisegit.git.git import GitRunner
from pytortoisegit.git.repo import Repository


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _make_repo(root, before, after):
    runner = GitRunner(cwd=str(root))
    runner.init(str(root), initial_branch="main")
    runner.run("config", "user.email", "t@example.com")
    runner.run("config", "user.name", "Tester")
    (root / "a.txt").write_text(before, encoding="utf-8")
    runner.run("add", "-A")
    runner.run("commit", "-m", "init")
    (root / "a.txt").write_text(after, encoding="utf-8")
    return Repository.open(str(root))


def _block_bg(view, index):
    from PySide6.QtGui import QTextCursor
    blk = view.document().findBlockByNumber(index)
    cur = QTextCursor(blk)
    cur.movePosition(QTextCursor.MoveOperation.Right,
                     QTextCursor.MoveMode.KeepAnchor)
    bg = cur.charFormat().background()
    return bg.color().name() if bg.style() else None


@pytest.fixture(scope="module")
def repo(tmp_path_factory):
    root = tmp_path_factory.mktemp("mergeview")
    before = "1\n2\n3\n4\n5\n6\n7\n8\n9\n10\n"
    after = "1\n2\n3\n4\nFIVE\n6\n7\n8\n9\n10\n"
    return _make_repo(root, before, after)


def test_diff_line_background_no_bleed(qapp, repo):
    """回归：改动行的背景色不能渗透到其后的普通行。"""
    from pytortoisegit.merge.mergefrm import MergeFrm
    frm = MergeFrm(repo, "a.txt", "HEAD", None)
    left, right = frm.left_view, frm.right_view

    normal_bg = _block_bg(left, 0)
    assert _block_bg(left, 4) != normal_bg     # 第 5 行 Removed
    assert _block_bg(right, 4) != normal_bg    # 第 5 行 Added
    # 其后的普通行必须回到默认背景（不得沿用改动色）
    for i in (0, 1, 2, 3, 5, 6, 7, 8, 9):
        assert _block_bg(left, i) == normal_bg, i
        assert _block_bg(right, i) == normal_bg, i


def test_identical_lines_not_marked_moved(qapp, repo):
    """回归：两侧相同的普通行不得被判为 MovedFrom/MovedTo（否则整段着色）。"""
    from pytortoisegit.merge.mergefrm import MergeFrm
    from pytortoisegit.merge.viewdata import DiffState
    frm = MergeFrm(repo, "a.txt", "HEAD", None)
    moved = {DiffState.MovedFrom, DiffState.MovedTo}
    for view in (frm.left_view, frm.right_view):
        for vd in view.view_data:
            assert vd.state not in moved, (vd.line, vd.state)
    # 只有真正变化的行有差异状态
    assert frm.left_view.view_data[4].state == DiffState.Removed
    assert frm.right_view.view_data[4].state == DiffState.Added


def test_real_moved_block_still_detected(tmp_path_factory, qapp):
    """真正的移动块（整段位移）仍应被识别为 MovedFrom/MovedTo。"""
    from pytortoisegit.merge.mergefrm import MergeFrm
    from pytortoisegit.merge.viewdata import DiffState
    root = tmp_path_factory.mktemp("mergeview_moved")
    before = "A\nB\nC\nD\nE\nF\nG\nH\n"
    after = "D\nE\nF\nG\nH\nA\nB\nC\n"
    repo = _make_repo(root, before, after)
    frm = MergeFrm(repo, "a.txt", "HEAD", None)
    left_states = [vd.state for vd in frm.left_view.view_data]
    right_states = [vd.state for vd in frm.right_view.view_data]
    assert DiffState.MovedFrom in left_states
    assert DiffState.MovedTo in right_states
    # D..H 未移动，保持普通
    assert left_states[3] == DiffState.Normal
