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
    runner.run("config", "core.autocrlf", "false")
    (root / "a.txt").write_bytes(before.encode("utf-8"))
    runner.run("add", "-A")
    runner.run("commit", "-m", "init")
    (root / "a.txt").write_bytes(after.encode("utf-8"))
    return Repository.open(str(root))


def _block_bg(view, index):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QTextCursor
    blk = view.document().findBlockByNumber(index)
    # 行背景现在用块格式（整行铺底），行内差异仍用字符格式
    bg = blk.blockFormat().background()
    if bg.style() != Qt.BrushStyle.NoBrush:
        return bg.color().name()
    cur = QTextCursor(blk)
    cur.movePosition(QTextCursor.MoveOperation.Right,
                     QTextCursor.MoveMode.KeepAnchor)
    cbg = cur.charFormat().background()
    return cbg.color().name() if cbg.style() != Qt.BrushStyle.NoBrush else None


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


def test_eol_difference_shown(tmp_path_factory, qapp):
    """换行符差异：默认忽略（不显示）；取消忽略后才检测并显示行尾标记。"""
    from pytortoisegit.merge.mergefrm import MergeFrm
    from pytortoisegit.merge.viewdata import DiffState, EOL
    root = tmp_path_factory.mktemp("mergeview_eol")
    repo = _make_repo(root, "line1\nline2\n", "line1\r\nline2\r\n")
    # 默认忽略换行符 → 不显示差异
    frm = MergeFrm(repo, "a.txt", "HEAD", None)
    assert frm.ignore_eol is True
    assert frm.left_view.view_data[0].state == DiffState.Normal
    assert "CRLF" not in frm.right_view.document().findBlockByNumber(0).text()
    # 取消忽略 → 检测并显示
    frm.ignore_eol = False
    frm._load()
    assert frm.left_view.view_data[0].ending == EOL.LF
    assert frm.right_view.view_data[0].ending == EOL.CRLF
    assert frm.left_view.view_data[0].state == DiffState.WhitespaceDiff
    assert frm.right_view.view_data[0].state == DiffState.WhitespaceDiff
    assert "CRLF" in frm.right_view.document().findBlockByNumber(0).text()
    assert "LF" in frm.left_view.document().findBlockByNumber(0).text()


def test_line_background_full_width(tmp_path_factory, qapp):
    """改动行背景铺满整行（块格式），普通行无背景（对齐 DrawSingleLine）。"""
    from PySide6.QtCore import Qt
    from pytortoisegit.merge.mergefrm import MergeFrm
    root = tmp_path_factory.mktemp("mergeview_fw")
    repo = _make_repo(root, "short\nsame\n", "SHORT\nsame\n")
    frm = MergeFrm(repo, "a.txt", "HEAD", None)
    frm.resize(600, 200)
    frm.show()
    qapp.processEvents()
    lv = frm.left_view
    doc = lv.document()

    def bg_of(text):
        for i in range(doc.blockCount()):
            b = doc.findBlockByNumber(i)
            if b.text() == text:
                return b.blockFormat().background()
        return None

    removed_bg = bg_of("short")
    assert removed_bg.style() != Qt.BrushStyle.NoBrush
    assert removed_bg.color().name() == "#ffc864"
    assert bg_of("same").style() == Qt.BrushStyle.NoBrush


def test_caret_line_sync(tmp_path_factory, qapp):
    """点击某一行 → 两个视图同步高亮该行。"""
    from pytortoisegit.merge.mergefrm import MergeFrm
    root = tmp_path_factory.mktemp("mergeview_caret")
    repo = _make_repo(root, "a\nb\nc\nd\ne\n", "A\nb\nC\nd\ne\n")
    frm = MergeFrm(repo, "a.txt", "HEAD", None)
    frm.show()
    qapp.processEvents()
    lv = frm.left_view
    blk = lv.document().findBlockByNumber(2)
    cur = lv.textCursor()
    cur.setPosition(blk.position())
    lv.setTextCursor(cur)
    qapp.processEvents()
    assert frm.left_view._current_line == 2
    assert frm.right_view._current_line == 2


def test_scroll_sync(tmp_path_factory, qapp):
    """滚轮/滚动条应同步左右视图（垂直与水平）。"""
    from pytortoisegit.merge.mergefrm import MergeFrm
    root = tmp_path_factory.mktemp("mergeview_scroll")
    before = "\n".join(f"line{i}" for i in range(200)) + "\n"
    after = "\n".join(f"LONG{i}" + "x" * 200 for i in range(200)) + "\n"
    repo = _make_repo(root, before, after)
    frm = MergeFrm(repo, "a.txt", "HEAD", None)
    frm.resize(500, 300)
    frm.show()
    qapp.processEvents()
    lb = frm.left_view.verticalScrollBar()
    rb = frm.right_view.verticalScrollBar()
    lb.setValue(40)
    qapp.processEvents()
    assert rb.value() == 40
    # 视口必须真正滚动（不只是滚动条数值）
    assert frm.left_view.firstVisibleBlock().blockNumber() == 40
    assert frm.right_view.firstVisibleBlock().blockNumber() == 40
    lh = frm.left_view.horizontalScrollBar()
    rh = frm.right_view.horizontalScrollBar()
    if lh.maximum() > 0:
        lh.setValue(min(10, lh.maximum()))
        qapp.processEvents()
        assert rh.value() == lh.value()


def test_locatorbar_stripes(qapp):
    """LocatorBar 支持左/右/底三条 stripe（对齐 CLocatorBar）。"""
    from pytortoisegit.merge.locatorbar import LocatorBar
    from pytortoisegit.merge.viewdata import DiffState
    lb = LocatorBar()
    lb.set_states([DiffState.Normal, DiffState.Removed],
                  [DiffState.Normal, DiffState.Added],
                  [DiffState.Normal, DiffState.Conflict])
    assert len(lb._stripes) == 3
    assert lb._total == 2
    # 只给左侧时仅一条
    lb.set_states([DiffState.Normal, DiffState.Added])
    assert len(lb._stripes) == 1


def test_mergefrm_statusbar_encoding(tmp_path_factory, qapp):
    """状态栏显示行尾与编码（对齐 CMainFrame）。"""
    from pytortoisegit.merge.mergefrm import MergeFrm
    from pytortoisegit.merge.eol import EOL
    from pytortoisegit.merge.filetextlines import UnicodeType
    root = tmp_path_factory.mktemp("mergeview_sb")
    repo = _make_repo(root, "a\nb\n", "a\nb\n")
    frm = MergeFrm(repo, "a.txt", "HEAD", None)
    frm.left_view.set_line_ending_style(EOL.CRLF)
    for vd in frm.left_view.view_data:
        vd.ending = EOL.CRLF
    frm.left_view.set_text_type(UnicodeType.UTF8)
    frm._update_statusbar_encoding()
    assert frm._eol_lab.text() == "CRLF"
    assert frm._enc_lab.text() == "UTF-8"


def test_mergefrm_recent_files(tmp_path_factory, qapp):
    from pytortoisegit.merge.mergefrm import MergeFrm
    root = tmp_path_factory.mktemp("mergeview_recent")
    repo = _make_repo(root, "a\n", "a\n")
    frm = MergeFrm(repo, "a.txt", "HEAD", None)
    assert frm.acceptDrops()
    frm.add_recent_file("/tmp/one.txt")
    frm.add_recent_file("/tmp/two.txt")
    rf = frm.recent_files()
    assert rf[0] == "/tmp/two.txt"
    assert rf[1] == "/tmp/one.txt"

