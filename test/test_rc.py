"""ui/rc.py 模板解析与排版换算测试。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from pytortoisegit.ui import rc

SRC_RC = (r"D:\work\ai\TortoiseGit-master\TortoiseGit-master"
          r"\src\Resources\TortoiseProcENG.rc")

SAMPLE = '''
IDD_SAMPLE DIALOGEX 0, 0, 300, 200
STYLE DS_SETFONT | DS_FIXEDSYS | WS_POPUP
CAPTION "Sample"
FONT 9, "Segoe UI", 400, 0, 0x1
BEGIN
    LTEXT           "&Name:",IDC_STATIC,7,7,40,10
    EDITTEXT        IDC_EDIT_NAME,50,5,200,12,ES_AUTOHSCROLL
    CONTROL         "&Flag",IDC_CHECK_FLAG,"Button",BS_AUTOCHECKBOX | WS_TABSTOP,7,24,100,10
    CONTROL         "",IDC_LIST,"SysListView32",LVS_REPORT | WS_BORDER | WS_TABSTOP,7,38,280,120
    GENERIC         "text with ""quotes""",IDC_X,CLS,STYLE,1,2,3,4
    PUSHBUTTON      "&OK",IDOK,70,160,50,14,WS_DISABLED
    DEFPUSHBUTTON   "Cancel",IDCANCEL,130,160,50,14
    GROUPBOX        "Wrap",IDC_GROUP,7,30,286,120
    CONTROL         "Hidden",IDC_HIDDEN,"Button",BS_AUTOCHECKBOX | NOT WS_VISIBLE,7,180,100,10
END
'''


_sample_parse = lambda: rc.parse_all(SAMPLE)["IDD_SAMPLE"]


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_sample_dialog_meta(qapp):
    d = _sample_parse()
    assert d.caption == "Sample"
    assert d.font, "Segoe UI"
    assert d.font_size == 9
    assert d.width == 300 and d.height == 200


def test_control_fields(qapp):
    d = _sample_parse()
    by_id = {c.ctrl_id: c for c in d.controls}
    assert by_id["IDC_EDIT_NAME"].kind == "EDITTEXT"
    assert by_id["IDC_EDIT_NAME"].x == 50 and by_id["IDC_EDIT_NAME"].h == 12
    assert by_id["IDC_CHECK_FLAG"].text == "&Flag"
    assert by_id["IDC_CHECK_FLAG"].cls == "Button"
    assert "BS_AUTOCHECKBOX" in by_id["IDC_CHECK_FLAG"].style
    assert by_id["IDC_LIST"].cls == "SysListView32"


def test_text_double_quote_escapes(qapp):
    d = _sample_parse()
    by_id = {c.ctrl_id: c for c in d.controls}
    assert by_id["IDC_X"].text == 'text with "quotes"'


def test_generic_kind_and_direct_coords(qapp):
    d = _sample_parse()
    by_id = {c.ctrl_id: c for c in d.controls}
    assert by_id["IDC_X"].kind == "GENERIC"
    assert (by_id["IDC_X"].x, by_id["IDC_X"].y,
            by_id["IDC_X"].w, by_id["IDC_X"].h) == (1, 2, 3, 4)


def test_hidden_flag(qapp):
    d = _sample_parse()
    by_id = {c.ctrl_id: c for c in d.controls}
    assert by_id["IDC_HIDDEN"].hidden
    assert not by_id["IDC_CHECK_FLAG"].hidden


def test_parse_real_rc_all_dialogs(qapp):
    text = open(SRC_RC, encoding="utf-8-sig").read()
    dlgs = rc.parse_all(text)
    assert len(dlgs) == 102
    assert "IDD_CHANGEDFILES" in dlgs
    d = dlgs["IDD_CHANGEDFILES"]
    ids = {c.ctrl_id for c in d.controls}
    assert {"IDC_BRANCH", "IDC_CHANGEDLIST", "IDC_BUTTON_UNIFIEDDIFF",
            "IDC_COMMIT", "IDOK"}.issubset(ids)
    hidden = {c.ctrl_id for c in d.controls if c.hidden}
    assert "IDC_SHOWUNMODIFIED" in hidden


def test_dialog_units_px(qapp):
    fu = rc.DialogUnits(9, "Segoe UI")
    r = fu.px(7, 14, 506, 152)
    assert r.width() > r.height()


def test_build_dialog_offscreen(qapp):
    from PySide6.QtWidgets import QPushButton, QLabel
    d = _sample_parse()
    w = rc.build_dialog(d)
    fu = rc.DialogUnits(d.font_size, d.font)
    counts = {"PUSHBUTTON": 0, "LTEXT": 0}
    for c in d.controls:
        wid = rc.make_widget(c)
        rc.place_widget(w, fu, c, wid)
        if isinstance(wid, QPushButton):
            counts["PUSHBUTTON"] += 1
        if isinstance(wid, QLabel):
            counts["LTEXT"] += 1
    assert counts["PUSHBUTTON"] >= 2
    assert counts["LTEXT"] >= 1
    wid = w.findChild(QPushButton, "IDOK")
    assert wid is not None
    assert not wid.isDefault()
    w.deleteLater()


def test_place_widget_clamps_combo_dropdown_height(qapp):
    """ComboBoxEx rc 高度是下拉列表，闭合态应压成单行。"""
    from PySide6.QtWidgets import QComboBox, QLineEdit
    d = _sample_parse()
    fu = rc.DialogUnits(d.font_size, d.font)
    dlg = rc.build_dialog(d)
    combo_ctrl = rc.Control(
        "CONTROL", "", "IDC_BRANCH_SOURCE", "ComboBoxEx32",
        "CBS_DROPDOWN", 76, 33, 198, 140)
    combo = QComboBox()
    rc.place_widget(dlg, fu, combo_ctrl, combo)
    full = fu.px(76, 33, 198, 140)
    assert combo.height() < full.height() / 3
    assert combo.height() <= fu.px(0, 0, 0, 22).height()
    edit_ctrl = rc.Control(
        "CONTROL", "", "IDC_URL", "ComboBoxEx32",
        "CBS_DROPDOWN", 76, 111, 218, 140)
    edit = QLineEdit()
    rc.place_widget(dlg, fu, edit_ctrl, edit)
    assert edit.height() < full.height() / 3
    dlg.deleteLater()


def test_defpushbutton_default(qapp):
    from PySide6.QtWidgets import QPushButton
    d = _sample_parse()
    fu = rc.DialogUnits(d.font_size, d.font)
    dlg = rc.build_dialog(d)
    w = None
    for c in d.controls:
        if c.ctrl_id == "IDCANCEL":
            w = rc.make_widget(c)
            rc.place_widget(dlg, fu, c, w)
    assert w is not None and w.isDefault()