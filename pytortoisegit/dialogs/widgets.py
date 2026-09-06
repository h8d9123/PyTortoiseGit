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

    # TortoiseGit TortoiseUDiff 配色（浅色默认 / 深色）
    LIGHT = dict(
        text="#0A2436", back="#ffffff",
        add_back="#CCFFCC", add_fore="#000000",
        del_back="#FFDDDD", del_fore="#000000",
        header_back="#FFFF80", header_fore="#800000",
        position_fore="#FF0000",
        comment_fore="#008000",
        command_back="#FFFFFF", command_fore="#0A2436",
    )
    DARK = dict(
        text="#DDDDDD", back="#202020",
        add_back="#104010", add_fore="#C8FFC8",
        del_back="#402020", del_fore="#FFC8C8",
        header_back="#303000", header_fore="#C00000",
        position_fore="#FF2020",
        comment_fore="#008000",
        command_back="#202020", command_fore="#CCE2F5",
    )

    def __init__(self, parent=None, monospace: bool = True):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        if monospace:
            f = QFont("Consolas" if __import__("sys").platform == "win32" else "monospace")
            f.setStyleHint(QFont.StyleHint.Monospace)
            f.setPointSize(10)
            self.setFont(f)
        self._loader = DiffHighlighter(self.document(), self._palette())

    @staticmethod
    def is_dark() -> bool:
        try:
            from PySide6.QtGui import QGuiApplication
            return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
        except Exception:
            return False

    def _palette(self) -> dict:
        return self.DARK if self.is_dark() else self.LIGHT

    def display_text(self, text: str, title: str = ""):
        self.clear()
        if title:
            self.appendPlainText(title)
        self.appendPlainText(text)
        self._loader.update_palette(self._palette())
        self._loader._rebuild()

    def display_patch(self, text: str, title: str = ""):
        self.display_text(text, title)


class DiffHighlighter(QSyntaxHighlighter):
    """按 diff 行类型着色（对齐 TortoiseGit TortoiseUDiff 的 SCE_DIFF_* 语义）。"""

    def __init__(self, document, palette: dict | None = None):
        super().__init__(document)
        self._lines: List[str] = []
        self.update_palette(palette or DiffView.LIGHT)

    def update_palette(self, p: dict):
        self._p = p
        fmt = QTextCharFormat()
        # 默认文本
        self._fmt_default = QTextCharFormat()
        self._fmt_default.setForeground(QColor(p["text"]))
        self._fmt_default.setBackground(QColor(p["back"]))
        # 添加行（SCE_DIFF_ADDED）
        self._fmt_add = QTextCharFormat()
        self._fmt_add.setBackground(QColor(p["add_back"]))
        self._fmt_add.setForeground(QColor(p["add_fore"]))
        # 删除行（SCE_DIFF_DELETED）
        self._fmt_del = QTextCharFormat()
        self._fmt_del.setBackground(QColor(p["del_back"]))
        self._fmt_del.setForeground(QColor(p["del_fore"]))
        # 位置行 @@（SCE_DIFF_POSITION）
        self._fmt_position = QTextCharFormat()
        self._fmt_position.setForeground(QColor(p["position_fore"]))
        # header（SCE_DIFF_HEADER）
        self._fmt_header = QTextCharFormat()
        self._fmt_header.setForeground(QColor(p["header_fore"]))
        self._fmt_header.setBackground(QColor(p["header_back"]))
        # 注释/元信息（diff --git / index / --- / +++）
        self._fmt_meta = QTextCharFormat()
        self._fmt_meta.setForeground(QColor(p["comment_fore"]))
        # 命令（+/- 行正文，与添加/删除同底色但更浅）
        self._fmt_cmd = QTextCharFormat()
        self._fmt_cmd.setForeground(QColor(p["command_fore"]))
        self._fmt_cmd.setBackground(QColor(p["command_back"]))

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
        n = len(line)
        if line.startswith("@@") or line.startswith("==="):
            self.setFormat(0, n, self._fmt_position)
        elif line.startswith(("diff --git", "index ")):
            self.setFormat(0, n, self._fmt_meta)
        elif line.startswith(("--- ", "+++ ", "new file", "old mode", "new mode")):
            self.setFormat(0, n, self._fmt_header)
        elif line.startswith("+"):
            self.setFormat(0, n, self._fmt_add)
        elif line.startswith("-"):
            self.setFormat(0, n, self._fmt_del)
        elif line.startswith("***"):
            self.setFormat(0, n, self._fmt_position)
        else:
            self.setFormat(0, n, self._fmt_default)


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