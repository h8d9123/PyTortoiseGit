"""MergeFrm 视图渲染：差异行背景色不得“渗透”到相邻行。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from pytortoisegit.git.git import GitRunner
from pytortoisegit.git.repo import Repository


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def repo(tmp_path_factory):
    root = tmp_path_factory.mktemp("mergeview")
    runner = GitRunner(cwd=str(root))
    runner.init(str(root), initial_branch="main")
    runner.run("config", "user.email", "t@example.com")
    runner.run("config", "user.name", "Tester")
    (root / "a.txt").write_text("line1\nline2\nline3\nline4\n", encoding="utf-8")
    runner.run("add", "-A")
    runner.run("commit", "-m", "init")
    (root / "a.txt").write_text(
        "line1\nline2-CHANGED\nline3\nline4\nline5-new\n", encoding="utf-8")
    return Repository.open(str(root))


def _block_bg(view, index):
    from PySide6.QtGui import QTextCursor
    doc = view.document()
    blk = doc.findBlockByNumber(index)
    cur = QTextCursor(blk)
    cur.movePosition(QTextCursor.MoveOperation.Right,
                     QTextCursor.MoveMode.KeepAnchor)
    bg = cur.charFormat().background()
    return bg.color().name() if bg.style() else None


def test_diff_line_background_no_bleed(qapp, repo):
    """回归：改动行的背景色不能渗透到其后的 Normal/Empty 行。"""
    from pytortoisegit.merge.mergefrm import MergeFrm
    frm = MergeFrm(repo, "a.txt", "HEAD", None)
    left = frm.left_view
    right = frm.right_view

    normal_bg = _block_bg(left, 0)          # line1 Normal
    removed_bg = _block_bg(left, 1)         # line2 Removed
    added_bg = _block_bg(right, 1)          # line2-CHANGED Added

    # 改动行应有区别于普通行的背景
    assert removed_bg != normal_bg
    assert added_bg != normal_bg
    # 其后的 Normal 行必须回到普通背景（不得沿用改动色）
    assert _block_bg(left, 2) == normal_bg
    assert _block_bg(left, 3) == normal_bg
    assert _block_bg(right, 2) == normal_bg
    assert _block_bg(right, 3) == normal_bg
    # 末尾 Empty 行也不得带改动色
    assert _block_bg(left, 4) == normal_bg
