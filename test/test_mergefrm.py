"""MergeFrm（内置合并/比较窗口）与 widgets（DiffView/高亮/RepoPickerRow）测试。"""

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog


@pytest.fixture(autouse=True)
def _english_ui():
    from pytortoisegit.res import strings
    strings.set_language("en")
    yield
    strings.set_language("zh")


@pytest.fixture(autouse=True)
def _no_modals(monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "warning",
                        staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))


# ===========================================================================
# widgets.py
# ===========================================================================

def test_diff_view_display(qapp):
    from pytortoisegit.dialogs.widgets import DiffView
    v = DiffView()
    v.display_text("+added\n-removed\n@@ -1 +1 @@\n", title="T")
    text = v.toPlainText()
    assert "T" in text and "+added" in text
    v.display_patch("+x\n")
    assert "+x" in v.toPlainText()
    assert isinstance(v._palette(), dict)


def test_diff_highlighter_blocks(qapp):
    from pytortoisegit.dialogs.widgets import DiffHighlighter, DiffView
    from PySide6.QtGui import QTextDocument
    doc = QTextDocument()
    h = DiffHighlighter(doc, DiffView.LIGHT)
    doc.setPlainText(
        "@@ -1 +1 @@\n"
        "diff --git a/x b/x\n"
        "index 123..456\n"
        "--- a/x\n"
        "+++ b/x\n"
        "+added\n"
        "-removed\n"
        "*** conflict\n"
        "context\n")
    h._rebuild()
    h.highlightBlock("")          # 空行直接返回
    h.update_palette(DiffView.DARK)
    h._rebuild()


def test_author_color_stable(qapp):
    from pytortoisegit.dialogs.widgets import author_color
    assert author_color("Alice").name() == author_color("Alice").name()
    assert author_color("").isValid()


def test_repo_picker_row(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    from pytortoisegit.dialogs.widgets import RepoPickerRow
    row = RepoPickerRow("Repo:")
    row.setText("C:/x")
    assert row.text() == "C:/x"
    fired = {}
    row.connect_editingFinished(lambda: fired.setdefault("y", True))
    row.edit.editingFinished.emit()
    assert fired.get("y")
    monkeypatch.setattr(QFileDialog, "getExistingDirectory",
                        staticmethod(lambda *a, **k: str(tmp_path)))
    row._browse()
    assert row.text() == str(tmp_path)


def test_build_diff_html(qapp):
    from pytortoisegit.dialogs.widgets import build_diff_html
    from pytortoisegit import udiff
    patch = udiff.parse_diff(
        "diff --git a/x.txt b/x.txt\n"
        "--- a/x.txt\n"
        "+++ b/x.txt\n"
        "@@ -1 +1 @@\n"
        "-old\n"
        "+new\n")[0]
    html = build_diff_html([patch])
    assert "<h3>" in html and "+new" in html


# ===========================================================================
# MergeFrm
# ===========================================================================

@pytest.fixture
def merge_repo(git_repo):
    (Path(git_repo.root) / "a.txt").write_text(
        "line1\nCHANGED\nline3\n", encoding="utf-8")
    return git_repo


def _frm(repo, **kw):
    from pytortoisegit.merge.mergefrm import MergeFrm
    return MergeFrm(repo, "a.txt", "HEAD", None, **kw)


def test_mergefrm_construct_and_load(qapp, merge_repo):
    frm = _frm(merge_repo)
    assert frm.left_view is not None and frm.right_view is not None
    assert frm.left_view.blockCount() >= 3
    assert frm._header.text()
    assert frm.left_view.toPlainText()


def test_mergefrm_toggles_and_header(qapp, merge_repo):
    frm = _frm(merge_repo)
    for fn in (frm._toggle_wrap, frm._toggle_linediff, frm._toggle_locator,
               frm._toggle_oneway, frm._toggle_show_ws, frm._toggle_inline,
               frm._toggle_inline_word, frm._toggle_moved,
               frm._toggle_ignore_comments, frm._toggle_ignore_eol,
               frm._toggle_toolbar, frm._toggle_statusbar, frm._toggle_collapse):
        fn(True)
        fn(False)
    frm._switch_left()
    frm._switch_left()
    frm._update_header()
    frm._refresh_linebar()
    frm._update_statusbar_encoding()
    frm._set_ws(frm.ignore_ws)
    frm._toggle_edit(False)


def test_mergefrm_navigation(qapp, merge_repo):
    frm = _frm(merge_repo)
    frm._goto_diff(1)
    frm._goto_diff(-1)
    frm._goto_inline(1)
    frm._goto_inline(-1)
    frm._goto_conflict(1)
    frm._current_line()
    frm._on_bar_click(0)
    frm._on_caret_line(0)
    frm._on_view_line(0)
    frm._bottom_data()


def test_mergefrm_find(qapp, merge_repo, monkeypatch):
    class _FakeFind:
        def __init__(self, *a, **k):
            self.search_down = True
            self.case_sensitive = False

        def exec(self):
            return 1

        def get_find_string(self):
            return "line"

    monkeypatch.setattr("pytortoisegit.merge.finddlg.FindDlg", _FakeFind)
    frm = _frm(merge_repo)
    frm._find()
    frm._find_next()
    frm._find_prev()
    frm._find_step(1)


def test_mergefrm_goto_line(qapp, merge_repo, monkeypatch):
    class _FakeGoto:
        def __init__(self, *a, **k):
            pass

        def exec(self):
            return 1

        def get_line_number(self):
            return 1

    monkeypatch.setattr("pytortoisegit.merge.gotolinedlg.GotoLineDlg", _FakeGoto)
    frm = _frm(merge_repo)
    frm._goto_line()


def test_mergefrm_use_blocks(qapp, merge_repo):
    frm = _frm(merge_repo)
    frm._on_use_left_block()
    frm._on_use_left_file()
    frm._on_use_both_left_first()
    frm._on_use_both_right_first()
    frm._on_use_theirs()
    frm._on_use_mine()
    frm._on_use_theirs_then()
    frm._on_use_mine_then()
    frm._undo()
    frm._redo()


def test_mergefrm_save_view_as(qapp, merge_repo, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QFileDialog
    frm = _frm(merge_repo)
    dest = tmp_path / "out.txt"
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: (str(dest), "")))
    assert frm._save_view_as(frm.left_view)
    assert dest.exists()


def test_mergefrm_create_patch(qapp, merge_repo, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QFileDialog
    frm = _frm(merge_repo)
    dest = tmp_path / "p.patch"
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: (str(dest), "")))
    frm._create_patch()


def test_mergefrm_recent_files(qapp, merge_repo):
    frm = _frm(merge_repo)
    frm.add_recent_file("C:/r/x.txt")
    assert "C:/r/x.txt" in frm.recent_files()
    frm._save_recent_files()
    frm._load_recent_files()


@pytest.fixture
def conflict_repo(git_repo):
    r = git_repo.runner
    root = Path(git_repo.root)
    r.run("checkout", "-b", "feature")
    (root / "a.txt").write_text("feature\n", encoding="utf-8")
    r.run("add", "-A")
    r.run("commit", "-m", "feature")
    r.run("checkout", "main")
    (root / "a.txt").write_text("main\n", encoding="utf-8")
    r.run("add", "-A")
    r.run("commit", "-m", "main")
    r.run("merge", "feature")
    return git_repo


def test_mergefrm_three_way_conflict(qapp, conflict_repo):
    from pytortoisegit.merge.mergefrm import MergeFrm
    frm = MergeFrm(conflict_repo, "a.txt", "MERGE_HEAD", None, three_way=True)
    assert frm.bottom_view is not None
    assert "Conflict" in frm._header.text()
    assert frm._has_unresolved() in (True, False)
    frm._goto_conflict(1)
    frm._on_use_left_block()
    frm._on_use_left_file()
    frm._on_use_both_left_first()
    frm._on_use_both_right_first()
    frm._on_use_theirs_then()
    frm._on_use_mine_then()


def test_mergefrm_three_way_save_merged(qapp, conflict_repo, monkeypatch,
                                        auto_progress):
    from pytortoisegit.merge.mergefrm import MergeFrm
    frm = MergeFrm(conflict_repo, "a.txt", "MERGE_HEAD", None, three_way=True)
    frm._on_use_left_file()            # 全部采用一侧 → 冲突清零
    assert not frm._has_unresolved()
    assert frm._conflicts_wont_keep() is False    # 无冲突不弹窗
    frm._save_merged(check_resolved=False)
    frm._mark_as_resolved_git()
    frm._mark_resolved()


def test_mergefrm_dialogs(qapp, merge_repo, monkeypatch):
    frm = _frm(merge_repo)

    class _FakeDlg:
        def __init__(self, *a, **k):
            pass

        def exec(self):
            return 0

    for path in ("pytortoisegit.merge.filepatchesdlg.FilePatchesDlg",
                 "pytortoisegit.merge.regexfiltersdlg.RegexFiltersDlg",
                 "pytortoisegit.merge.settings.Settings",
                 "pytortoisegit.merge.aboutdlg.AboutDlg"):
        monkeypatch.setattr(path, _FakeDlg)
    frm._show_filelist()
    frm._regex_filter()
    frm._settings()
    frm._about()
    frm._help()


def test_mergefrm_drag_drop(qapp, merge_repo):
    from PySide6.QtGui import QDropEvent
    from PySide6.QtCore import QMimeData, QPointF, QUrl
    frm = _frm(merge_repo)
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(Path(merge_repo.root) / "a.txt"))])

    class _Ev:
        def acceptProposedAction(self):
            pass

        def mimeData(self):
            return mime

    frm.dragEnterEvent(_Ev())
    frm.dropEvent(_Ev())


def test_mergefrm_local_diff(qapp, tmp_path):
    from pytortoisegit.merge.mergefrm import MergeFrm
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_text("same\nold\n", encoding="utf-8")
    b.write_text("same\nnew\n", encoding="utf-8")
    frm = MergeFrm(None, "", None, None)
    frm._local_left, frm._local_right = str(a), str(b)
    frm._load()
    assert frm.left_view.blockCount() >= 2
