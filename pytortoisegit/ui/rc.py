"""ui/rc.py —— TortoiseGit .rc 对话框模板的解析与 Qt 排版复刻。

从 TortoiseProcENG.rc 提取对话框模板（DLOG 单位 DLU），再用对话框字体
实测换算成像素，绝对定位构建控件，忠实现 TortoiseGit 的布局。

.rc 语法要点：
  * 语句行以逗号结尾时续行（如 CONTROL 的分行写法）
  * 控件行格式：KIND "text",ID,"class",styles,x,y,w,h[,extstyles]
"""

# PyTortoiseGit - a Python reimplementation mirroring TortoiseGit.
# Copyright (C) 2026  PyTortoiseGit contributors
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# This program is derived from and mirrors the TortoiseGit project.

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# 解析
# ---------------------------------------------------------------------------

_DIALOG_HEADER_RE = re.compile(
    r'^(?P<id>IDD_\w+)\s+DIALOGEX\s+[-\d]+,\s*[-\d]+,\s*'
    r'(?P<w>\d+),\s*(?P<h>\d+)\s*$')


@dataclass
class Control:
    kind: str            # CONTROL / LTEXT / RTEXT / CTEXT / EDITTEXT / ...
    text: str
    ctrl_id: str
    cls: str
    style: str
    x: int
    y: int
    w: int
    h: int
    ex_style: str = ""
    hidden: bool = False

    @property
    def rect(self):
        return (self.x, self.y, self.w, self.h)


@dataclass
class Dialog:
    id: str
    width: int
    height: int
    caption: str = ""
    font: str = ""
    font_size: int = 8
    style: str = ""
    controls: List[Control] = field(default_factory=list)


def _join_lines(text: str) -> str:
    lines = text.splitlines()
    out: List[str] = []
    buf = ""
    for ln in lines:
        ln = ln.rstrip()
        buf += ln
        if not ln.endswith(","):
            out.append(buf)
            buf = ""
    if buf:
        out.append(buf)
    return "\n".join(out)


_TOKEN_RE = re.compile(r'"(?:[^"\\]|""|\\.)*"|[^\s,]+')
_NUM_RE = re.compile(r'-?\d+')


def _split_rc(line: str) -> List[str]:
    return [t.rstrip(",") for t in _TOKEN_RE.findall(line) if t != ","]


def _is_num(tok: str) -> bool:
    return bool(_NUM_RE.fullmatch(tok))


def _coords_at(toks: List[str], start: int) -> Optional[int]:
    """返回第一个连续 4 个都是数字的坐标起点，找不到返回 None。"""
    for j in range(start, len(toks) - 3):
        if all(_is_num(t) for t in toks[j:j + 4]):
            return j
    return None


def _parse_control(line: str) -> Optional[Control]:
    toks = _split_rc(line)
    if len(toks) < 6:
        return None
    kind = toks[0]
    text = ""
    i = 1
    if toks[i].startswith('"'):
        text = toks[i][1:-1]
        i += 1
    ctrl_id = toks[i]
    i += 1
    cls = ""
    if kind == "CONTROL" and toks[i].startswith('"'):
        cls = toks[i][1:-1]
        i += 1
    ci = _coords_at(toks, i)
    if ci is None:
        return None
    x, y, w, h = (int(t) for t in toks[ci:ci + 4])
    style = " ".join(toks[i:ci]).strip()
    ex = " ".join(toks[ci + 4:]).strip()
    if not style and cls:
        style = cls
    ctrl = Control(
        kind=kind,
        text=text.replace('""', '"'),
        ctrl_id=ctrl_id,
        cls=cls,
        style=_norm_style(style, ctrl_id),
        x=x, y=y, w=w, h=h,
        ex_style=ex,
    )
    if "NOT WS_VISIBLE" in style + ex or "not visible" in (style + ex).lower():
        ctrl.hidden = True
    return ctrl


def _norm_style(style: str, id: str) -> str:
    if id.upper() in ("IDOK", "IDCANCEL", "IDHELP") and not style.startswith("BS_"):
        return "BS_DEFPUSHBUTTON"
    return style


def _parse_head(dlg: Dialog, seg: List[str]) -> None:
    head = "\n".join(seg)
    fm = re.search(r'CAPTION\s+"((?:[^"\\]|\\.)*)"', head)
    if fm:
        dlg.caption = fm.group(1)
    fp = re.search(r'FONT\s+(\d+)\s*,\s*"([^"]*)"', head)
    if fp:
        dlg.font_size = int(fp.group(1))
        dlg.font = fp.group(2)
    st = re.search(r'STYLE\s+([\w\s|]+)', head)
    if st:
        dlg.style = st.group(1)


def _parse_body(dlg: Dialog, body: List[str]) -> None:
    used: set = set()
    for line in _join_lines("\n".join(body)).splitlines():
        line = line.strip()
        if not line:
            continue
        ctrl = _parse_control(line)
        if not ctrl:
            continue
        if ctrl.ctrl_id in used:
            continue
        used.add(ctrl.ctrl_id)
        dlg.controls.append(ctrl)


def _extract(text: str) -> List[Tuple[Dialog, List[str]]]:
    out: List[Tuple[Dialog, List[str]]] = []
    lines = text.splitlines()
    n = len(lines)
    for idx in range(n):
        hm = _DIALOG_HEADER_RE.match(lines[idx])
        if not hm:
            continue
        dlg = Dialog(id=hm.group("id"), width=int(hm.group("w")),
                     height=int(hm.group("h")))
        head: List[str] = []
        base: List[str] = []
        started = False
        for j in range(idx + 1, n):
            ln = lines[j]
            if not started:
                if ln.strip() == "BEGIN":
                    started = True
                else:
                    head.append(ln)
            else:
                if ln.strip() == "END":
                    break
                base.append(ln)
        _parse_head(dlg, head)
        _parse_body(dlg, base)
        out.append((dlg, base))
    return out


def parse_all(text: str) -> Dict[str, Dialog]:
    return {dlg.id: dlg for dlg, _ in _extract(text)}


def _control_from_dict(d: dict) -> Control:
    return Control(
        kind=d.get("k", "LTEXT"),
        text=d.get("t", ""),
        ctrl_id=d.get("id", ""),
        cls=d.get("c", ""),
        style=d.get("s", ""),
        x=d.get("x", 0), y=d.get("y", 0),
        w=d.get("w", 0), h=d.get("h", 0),
        ex_style=d.get("ex", ""),
        hidden=d.get("hidden", False),
    )


def load_json(obj) -> Dict[str, Dialog]:
    """把 extract_rc.py 生成的 rc_dialogs.json 还原成 Dialog 对象。"""
    dialogs: Dict[str, Dialog] = {}
    for d in obj:
        dlg = Dialog(
            id=d.get("id", ""),
            width=d.get("w", 0),
            height=d.get("h", 0),
            caption=d.get("caption", ""),
            font=d.get("font", ""),
            font_size=d.get("font_size", 8),
            style=d.get("style", ""),
            controls=[_control_from_dict(c) for c in d.get("controls", [])],
        )
        dialogs[dlg.id] = dlg
    return dialogs


_JSON_PATH = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "res", "rc_dialogs.json")


def load_spec(dialog_id: str) -> Dialog:
    """从内置 rc_dialogs.json 获取一个对话框模板。"""
    with open(_JSON_PATH, encoding="utf-8-sig") as fh:
        dialogs = load_json(json.load(fh))
    return dialogs[dialog_id]


# ---------------------------------------------------------------------------
# DLU -> 像素
# ---------------------------------------------------------------------------

class DialogUnits:
    """用对话框字体实测基单位，把 DLU 映射为像素。

    MFC 规则：baseunitX = 平均字符宽，baseunitY = 字符高度；
    像素 = DLU * baseunit / (4 for X, 8 for Y)。
    """

    def __init__(self, font_size: int = 9, font_family: str = "Segoe UI"):
        self.base_x: float
        self.base_y: float
        self._measure(font_size, font_family)

    def _measure(self, size: int, family: str):
        from PySide6.QtGui import QFont, QFontMetrics
        f = QFont(family)
        f.setPointSize(size)
        f.setStyleHint(QFont.StyleHint.Helvetica)
        fm = QFontMetrics(f)
        sample = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        self.base_x = fm.horizontalAdvance(sample) / 26.0
        self.base_y = float(fm.height())

    def px(self, x: int, y: int, w: int, h: int):
        from PySide6.QtCore import QRect
        return QRect(
            int(x * self.base_x / 4.0), int(y * self.base_y / 8.0),
            int(w * self.base_x / 4.0), int(h * self.base_y / 8.0))


# ---------------------------------------------------------------------------
# 构建
# ---------------------------------------------------------------------------

_BUTTON_KINDS = {"PUSHBUTTON", "DEFPUSHBUTTON"}
_EXCLUDE_IDS = {"IDSTATIC", "IDC_STATIC"}


def build_dialog(spec: Dialog, parent=None):
    """按模板尺寸建一个 QDialog（仅外框与字体）。"""
    from PySide6.QtWidgets import QDialog
    fu = DialogUnits(spec.font_size or 9, spec.font or "Segoe UI")
    r = fu.px(0, 0, spec.width, spec.height)
    dlg = QDialog(parent)
    dlg.resize(int(r.width()), int(r.height()))
    if spec.caption:
        dlg.setWindowTitle(spec.caption)
    font = dlg.font()
    font.setPointSize(spec.font_size or 9)
    dlg.setFont(font)
    return dlg


# Win32 ComboBox/ComboBoxEx 的 rc 高度是下拉列表高度，闭合态约等于按钮（14 DLU）
_CLOSED_COMBO_DLU = 14
_COMBO_CLASSES = {"ComboBox", "ComboBoxEx32"}
_COMBO_KINDS = {"COMBOBOX"}


def _is_combo_template(ctrl: Control) -> bool:
    return ctrl.cls in _COMBO_CLASSES or ctrl.kind in _COMBO_KINDS


def _closed_field_height(fu: DialogUnits, widget) -> int:
    closed = fu.px(0, 0, 0, _CLOSED_COMBO_DLU).height()
    hint = widget.sizeHint().height() if hasattr(widget, "sizeHint") else 0
    return max(closed, hint) if hint > 0 else closed


def place_widget(dlg, fu: DialogUnits, ctrl: Control, widget) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QComboBox, QLabel, QLineEdit, QWidget
    r = fu.px(ctrl.x, ctrl.y, ctrl.w, ctrl.h)
    combo_like = _is_combo_template(ctrl) or isinstance(widget, QComboBox)
    single_line = isinstance(widget, QLineEdit)
    if (combo_like or single_line) and ctrl.h > 20:
        r.setHeight(_closed_field_height(fu, widget))
        if isinstance(widget, QComboBox):
            extra = max(ctrl.h - _CLOSED_COMBO_DLU, 30)
            widget.setMaxVisibleItems(max(8, extra // 12))
    widget.setParent(dlg)
    widget.setObjectName(ctrl.ctrl_id)
    if isinstance(widget, QWidget):
        font = widget.font()
        font.setPointSize(dlg.font().pointSize())
        widget.setFont(font)
    # 单行标签：DLU 高度按西文行高换算，回退/CJK 字体行高更大时底部会被裁切，
    # 这里保证至少容纳实际文本高度（对齐 Windows 显示）。
    if isinstance(widget, QLabel) and not widget.wordWrap() and not ctrl.hidden:
        r.setHeight(max(r.height(), widget.sizeHint().height()))
    widget.setGeometry(r)
    if ctrl.hidden:
        widget.hide()
    widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)


def make_widget(ctrl: Control, parent=None):
    """按控件类型创建默认 Qt 控件（尽量贴近 MFC 外观）。"""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QCheckBox, QComboBox, QDateTimeEdit, QFrame, QGroupBox, QLabel,
        QLineEdit, QPlainTextEdit, QProgressBar, QPushButton, QRadioButton,
        QTreeWidget)
    kind, cls, style, ctrl_id = ctrl.kind, ctrl.cls, ctrl.style, ctrl.ctrl_id
    text = ctrl.text
    if kind in _BUTTON_KINDS:
        b = QPushButton(text if text else "OK" if ctrl_id == "IDOK" else "")
        b.setDefault(kind == "DEFPUSHBUTTON")
        return b
    if kind == "GROUPBOX":
        return QGroupBox(text, parent)
    if kind in ("LTEXT", "RTEXT", "CTEXT") or (cls == "Static"
                                               and "SS_BLACKFRAME" not in style):
        label = QLabel(parent)
        if kind == "RTEXT":
            label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        elif kind == "CTEXT":
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return label
    if cls == "Static" and "SS_BLACKFRAME" in style:
        f = QFrame(parent)
        f.setFrameShape(QFrame.Shape.HLine)
        return f
    if kind == "EDITTEXT" or cls == "Edit":
        if "ES_MULTILINE" in style:
            return QPlainTextEdit(parent)
        return QLineEdit(parent)
    if kind == "COMBOBOX" or cls in ("ComboBox", "ComboBoxEx32"):
        return QComboBox(parent)
    if kind == "CHECKBOX":
        return QCheckBox(text, parent)
    if kind == "RADIOBUTTON":
        return QRadioButton(text, parent)
    if cls == "SysListView32":
        return QTreeWidget(parent)
    if cls == "SysTreeView32":
        return QTreeWidget(parent)
    if cls == "SysDateTimePick32":
        return QDateTimeEdit(parent)
    if cls == "msctls_progress32":
        return QProgressBar(parent)
    if cls == "Button":
        if "BS_AUTOCHECKBOX" in style or "BS_AUTO3STATE" in style:
            return QCheckBox(text, parent)
        if "BS_AUTORADIOBUTTON" in style:
            return QRadioButton(text, parent)
        return QPushButton(text, parent)
    return QLabel(parent)