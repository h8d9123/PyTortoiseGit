# PyTortoiseGit - a Python reimplementation mirroring TortoiseGit.
# Copyright (C) 2026  PyTortoiseGit contributors
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.

"""ribbon.py —— 对齐 TortoiseGitMerge 的 UIRibbon（TortoiseGitMergeRibbon.xml）。

原版默认 UseRibbons=TRUE：无经典菜单栏。
  * Application Menu（文件）：Open/Save/SaveAs、Create patch、File list、Settings、About、Exit
  * 唯一 Tab「Edit」分组：Edit / Navigate / Blocks / Whitespaces / Diff / View
  * Quick Access：Save / Undo / Redo
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMenu, QScrollArea, QSizePolicy, QToolButton,
    QVBoxLayout, QWidget,
)

from ..res.strings import tr


def _icon(name: str):
    if not name:
        return None
    try:
        from ..res import icons
        ic = icons.icon(name)
        return ic if ic and not ic.isNull() else None
    except Exception:
        return None


def _tool(act: QAction, large: bool = False) -> QToolButton:
    btn = QToolButton()
    btn.setDefaultAction(act)
    btn.setAutoRaise(True)
    if large:
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        btn.setIconSize(QSize(28, 28))
        btn.setMinimumSize(48, 56)
        btn.setMaximumWidth(76)
    else:
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        btn.setIconSize(QSize(16, 16))
        btn.setMinimumHeight(22)
    return btn


class _Group(QFrame):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("RibbonGroup")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 2)
        lay.setSpacing(2)
        self.body = QHBoxLayout()
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(2)
        lay.addLayout(self.body, 1)
        cap = QLabel(title, self)
        cap.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
        cap.setObjectName("RibbonGroupCaption")
        lay.addWidget(cap)

    def add(self, w):
        self.body.addWidget(w, 0, Qt.AlignmentFlag.AlignTop)

    def add_col(self, widgets):
        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(1)
        for w in widgets:
            col.addWidget(w)
        col.addStretch(1)
        self.body.addLayout(col)


class MergeRibbon(QWidget):
    """TortoiseGitMerge Ribbon 主体（替换 QMenuBar）。"""

    def __init__(self, actions: dict[str, QAction], parent=None):
        super().__init__(parent)
        self.setObjectName("MergeRibbon")
        self._acts = actions
        self._build()
        self.setStyleSheet("""
            QWidget#MergeRibbon { background: #f0f0f0; }
            QFrame#RibbonGroup {
                background: #f7f7f7;
                border-right: 1px solid #cfcfcf;
            }
            QLabel#RibbonGroupCaption {
                color: #5a5a5a;
                font-size: 11px;
            }
            QToolButton#RibbonFile {
                background: #c65d12;
                color: white;
                font-weight: bold;
                padding: 4px 16px;
                border: none;
            }
            QToolButton#RibbonFile:hover { background: #e07020; }
            QLabel#RibbonTab {
                color: #1a5fb4;
                font-weight: bold;
                padding: 4px 14px 6px 14px;
                border-bottom: 2px solid #1a5fb4;
            }
            QFrame#RibbonQat { background: #e8e8e8; }
        """)

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._qat())
        root.addWidget(self._tabs())
        root.addWidget(self._edit_tab())

    def _qat(self) -> QWidget:
        bar = QFrame(self)
        bar.setObjectName("RibbonQat")
        h = QHBoxLayout(bar)
        h.setContentsMargins(6, 2, 6, 2)
        h.setSpacing(2)
        for key in ("save", "undo", "redo"):
            btn = QToolButton(bar)
            btn.setDefaultAction(self._acts[key])
            btn.setAutoRaise(True)
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            h.addWidget(btn)
        h.addStretch(1)
        return bar

    def _tabs(self) -> QWidget:
        row = QWidget(self)
        h = QHBoxLayout(row)
        h.setContentsMargins(4, 0, 8, 0)
        h.setSpacing(0)
        file_btn = QToolButton(row)
        file_btn.setObjectName("RibbonFile")
        file_btn.setText(tr("tm_file_tab", "文件"))
        file_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        file_btn.setMenu(self._file_menu())
        h.addWidget(file_btn)
        tab = QLabel(tr("tm_edit_tab", "编辑"), row)
        tab.setObjectName("RibbonTab")
        h.addWidget(tab)
        h.addStretch(1)
        help_btn = QToolButton(row)
        help_btn.setDefaultAction(self._acts["help"])
        help_btn.setAutoRaise(True)
        help_btn.setText("?")
        help_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        h.addWidget(help_btn)
        return row

    def _file_menu(self) -> QMenu:
        """ApplicationMenu：对齐 Ribbon.ApplicationMenu 分组。"""
        m = QMenu(self)
        m.addAction(self._acts["open"])
        m.addAction(self._acts["save"])
        m.addAction(self._acts["saveas"])
        m.addSeparator()
        m.addAction(self._acts["patch"])
        m.addSeparator()
        m.addAction(self._acts["filelist"])
        m.addAction(self._acts["settings"])
        m.addSeparator()
        m.addAction(self._acts["about"])
        m.addSeparator()
        m.addAction(self._acts["exit"])
        return m

    def _split(self, main: QAction, extras: list[QAction]) -> QToolButton:
        btn = _tool(main, large=True)
        btn.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        menu = QMenu(btn)
        for a in extras:
            menu.addAction(a)
        btn.setMenu(menu)
        return btn

    def _edit_tab(self) -> QWidget:
        a = self._acts
        strip = QWidget(self)
        h = QHBoxLayout(strip)
        h.setContentsMargins(0, 0, 0, 4)
        h.setSpacing(0)

        g = _Group(tr("tm_group_edit", "编辑"), strip)
        g.add(_tool(a["save"], True))
        g.add(_tool(a["reload"], True))
        g.add_col([_tool(a["undo"]), _tool(a["redo"]), _tool(a["enable_edit"])])
        g.add(_tool(a["copy"], True))
        g.add(_tool(a["paste"], True))
        g.add(_tool(a["find"], True))
        g.add_col([_tool(a["find_prev"]), _tool(a["find_next"])])
        g.add(_tool(a["goto"], True))
        g.add(_tool(a["mark"], True))
        h.addWidget(g)

        g = _Group(tr("tm_group_nav", "导航"), strip)
        g.add_col([_tool(a["prev_diff"]), _tool(a["prev_conf"]), _tool(a["prev_inline"])])
        g.add_col([_tool(a["next_diff"]), _tool(a["next_conf"]), _tool(a["next_inline"])])
        h.addWidget(g)

        g = _Group(tr("tm_group_blocks", "块"), strip)
        g.add(self._split(a["use_left_block"], [
            a["use_left_file"], a["use_left_before"], a["use_right_before"]]))
        g.add(self._split(a["use_theirs"], [
            a["use_mine"], a["use_theirs_then"], a["use_mine_then"]]))
        h.addWidget(g)

        g = _Group(tr("tm_group_ws", "空白"), strip)
        g.add(_tool(a["show_ws"], True))
        g.add(_tool(a["cmp_ws"], True))
        g.add(_tool(a["ign_ws"], True))
        g.add(_tool(a["ign_all_ws"], True))
        h.addWidget(g)

        g = _Group(tr("tm_group_diff", "差异"), strip)
        g.add(_tool(a["inline"], True))
        g.add(_tool(a["inline_word"], True))
        g.add(_tool(a["regex"], True))
        g.add(_tool(a["ignore_comments"], True))
        g.add(_tool(a["ignore_eol"], True))
        h.addWidget(g)

        g = _Group(tr("tm_group_view", "视图"), strip)
        bars = _tool(a["view_bars"], True)
        bars.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        bars_menu = QMenu(bars)
        bars_menu.addAction(a["linediffbar"])
        bars_menu.addAction(a["locator"])
        bars_menu.addAction(a["statusbar"])
        bars.setMenu(bars_menu)
        g.add(bars)
        g.add(_tool(a["wrap"], True))
        g.add(_tool(a["oneway"], True))
        g.add(_tool(a["switch"], True))
        g.add(_tool(a["collapse"], True))
        h.addWidget(g)

        h.addStretch(1)
        strip.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        sc = QScrollArea(self)
        sc.setWidget(strip)
        sc.setWidgetResizable(False)
        sc.setFrameShape(QFrame.Shape.NoFrame)
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        sc.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sc.setFixedHeight(strip.sizeHint().height() + 8)
        return sc
