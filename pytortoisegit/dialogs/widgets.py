"""widgets.py —— 对话框共用的显示组件（diff 渲染、作者配色、路径选择）。"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import udiff as udiff_mod


class DiffView(QPlainTextEdit):
    """渲染统一 diff 文本，带行级着色。"""

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

    COLORS = {
        "addition": QColor("#223322"),
        "deletion": QColor("#332222"),
        "hunk": QColor("#d8a000"),
        "meta": QColor("#777777"),
    }

    def __init__(self, parent=None, monospace: bool = True):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        if monospace:
            f = QFont("Consolas" if __import__("sys").platform == "win32" else "monospace")
            f.setStyleHint(QFont.StyleHint.Monospace)
            f.setPointSize(10)
            self.setFont(f)
        self._loader = DiffHighlighter(self.document())

    def display_text(self, text: str, title: str = ""):
        self.clear()
        if title:
            self.appendPlainText(title)
        self.appendPlainText(text)
        self._loader._rebuild()

    def display_patch(self, text: str, title: str = ""):
        self.display_text(text, title)


class DiffHighlighter(QSyntaxHighlighter):
    """按 diff 行类型着色。"""

    def __init__(self, document):
        super().__init__(document)
        self._cache: List[tuple] = []
        fmt = QTextCharFormat()
        self._fmt_add = QTextCharFormat()
        self._fmt_add.setBackground(QColor("#2a3a2a"))
        self._fmt_add.setForeground(QColor("#9fdc9f"))
        self._fmt_del = QTextCharFormat()
        self._fmt_del.setBackground(QColor("#3a2a2a"))
        self._fmt_del.setForeground(QColor("#f0b0b0"))
        self._fmt_hunk = QTextCharFormat()
        self._fmt_hunk.setForeground(QColor("#e0a000"))
        self._fmt_meta = QTextCharFormat()
        self._fmt_meta.setForeground(QColor("#888888"))
        self._lines: List[str] = []

    def _rebuild(self):
        doc = self.document()
        self._lines = doc.toPlainText().splitlines()
        self.rehighlight()

    def highlightBlock(self, text: str):
        if not text:
            return
        idx = self.currentBlock().blockNumber()
        try:
            line = self._lines[idx]
        except IndexError:
            line = text
        if line.startswith("@@") or line.startswith("==="):
            self.setFormat(0, len(line), self._fmt_hunk)
        elif line.startswith("+"):
            self.setFormat(0, len(line), self._fmt_del if False else self._fmt_add)
        elif line.startswith("-"):
            self.setFormat(0, len(line), self._fmt_del)
        elif line.startswith(("diff --git", "index ", "---", "+++", "new file", "old mode", "new mode")):
            self.setFormat(0, len(line), self._fmt_meta)
        elif line.startswith("***"):
            self.setFormat(0, len(line), self._fmt_hunk)


def author_color(author_name: str) -> QColor:
    """按作者名生成稳定颜色，用于 blame/日志着色。"""
    palette = [
        "#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f",
        "#edc948", "#b07aa1", "#ff9da7", "#9c755f", "#bab0ab",
    ]
    total = sum(ord(c) for c in author_name) if author_name else 0
    return QColor(palette[total % len(palette)])


class RepoPickerRow(QWidget):
    """文件夹选择行：文本框 + 浏览按钮。"""

    def __init__(self, label: str = "", parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self._label = QLabel(label, self)
        lay.addWidget(self._label)
        self.edit = QLineEdit(self)
        lay.addWidget(self.edit, 1)
        btn = QPushButton("…", self)
        btn.setFixedWidth(28)
        btn.clicked.connect(self._browse)
        lay.addWidget(btn)

    def _browse(self):
        path = QFileDialog.getExistingDirectory(self, "选择文件夹", self.edit.text())
        if path:
            self.edit.setText(path)

    def text(self) -> str:
        return self.edit.text().strip()

    def setText(self, value: str):
        self.edit.setText(value)

    def connect_editingFinished(self, on_finish):
        self.edit.editingFinished.connect(on_finish)


def build_diff_html(patches: Sequence[udiff_mod.FilePatch]) -> str:
    """把补丁转成 HTML（备选展示，一般不直接用）。"""
    parts: List[str] = []
    for patch in patches:
        parts.append(f"<h3>{patch.filename_display}</h3>")
        for hunk in patch.hunks:
            parts.append(f"<pre>{hunk.header}</pre>")
            for ln in hunk.lines:
                cls = "add" if ln.is_addition else ("del" if ln.is_deletion else "ctx")
                parts.append(f'<pre class="{cls}">{ln.kind}{ln.content}</pre>')
    return "\n".join(parts)