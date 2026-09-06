"""sbsdiffdlg.py —— SideBySideDiffDlg：并排 diff 比较对话框（对齐 TortoiseGitMerge）。

左栏 = 旧版本（rev1 / base），右栏 = 新版本（rev2 / target）。
基于统一 diff 做行级对齐着色：删除行（左栏红底）、新增行（右栏绿底）、
修改行（两侧高亮），并同步滚动。
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QSplitter,
    QVBoxLayout,
)

from ..git.repo import Repository
from ..res.strings import tr
from ..udiff import parse_diff
from .widgets import DiffView


def _read_content(repo: Repository, rev: str | None, path: str) -> List[str]:
    """读某修订下文件的行列表；rev=None 时读工作区。"""
    if rev:
        out = repo.runner.run("show", f"{rev}:{path}").stdout
    else:
        out = repo.runner.run("cat-file", "-p", f"HEAD:{path}").stdout
    if not out:
        return []
    return out.splitlines()


class SideBySideDiffDlg(QDialog):
    """左右并排比较两个修订的单个文件。"""

    def __init__(self, repo: Repository, path: str, rev1: str | None,
                 rev2: str | None, parent=None, title: str = ""):
        super().__init__(parent, Qt.WindowType.Window)
        self.repo = repo
        self.path = path
        self.rev1 = rev1
        self.rev2 = rev2
        self.setWindowTitle(title or tr("sbs_diff_title", "比较 - {}").format(path))
        self.resize(960, 620)
        self._build_ui()
        self._load_diff()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        self._header = QLabel("", self)
        self._header.setWordWrap(True)
        lay.addWidget(self._header)

        split = QSplitter(Qt.Orientation.Horizontal, self)
        left_w = QVBoxLayout()
        left_w.setContentsMargins(0, 0, 0, 0)
        left_w.addWidget(QLabel(tr("sbs_old", "旧版本"), self))
        self.left_view = QPlainTextEdit(self)
        self.left_view.setReadOnly(True)
        self.left_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        left_w.addWidget(self.left_view)
        left_box = _wrap(self, left_w)
        split.addWidget(left_box)

        right_w = QVBoxLayout()
        right_w.setContentsMargins(0, 0, 0, 0)
        right_w.addWidget(QLabel(tr("sbs_new", "新版本"), self))
        self.right_view = QPlainTextEdit(self)
        self.right_view.setReadOnly(True)
        self.right_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        right_w.addWidget(self.right_view)
        right_box = _wrap(self, right_w)
        split.addWidget(right_box)

        mono = QFont("Consolas" if __import__("sys").platform == "win32" else "monospace")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        mono.setPointSize(10)
        self.left_view.setFont(mono)
        self.right_view.setFont(mono)

        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 1)
        lay.addWidget(split, 1)

        # 同步滚动
        self.left_view.verticalScrollBar().valueChanged.connect(
            self.right_view.verticalScrollBar().setValue)
        self.right_view.verticalScrollBar().valueChanged.connect(
            self.left_view.verticalScrollBar().setValue)

        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        box.rejected.connect(self.reject)
        box.button(QDialogButtonBox.StandardButton.Close).setText(tr("close"))
        lay.addWidget(box)

    def _load_diff(self):
        # 取两栏内容
        old_lines = _read_content(self.repo, self.rev1, self.path)
        new_lines = _read_content(self.repo, self.rev2, self.path)
        # 构造 git diff 命令
        args = ["diff", "--no-color", "-U0"]
        if self.rev1 and self.rev2:
            args += [self.rev1, self.rev2]
        elif self.rev2:
            args += [self.rev2]
        elif self.rev1:
            args += [self.rev1]
        args += ["--", self.path]
        patch_text = self.repo.runner.run(*args).stdout or ""
        patches = parse_diff(patch_text)
        # 找到目标文件 patch（可能无差异）
        target = next((p for p in patches if p.filename_display == self.path or
                       self.path.endswith(p.filename_display)), None)

        # 收集行着色
        add_mask = {}   # 右栏新文件行号 -> True (新增/修改)
        del_mask = {}   # 左栏旧文件行号 -> True (删除/修改)
        if target is not None:
            for h in target.hunks:
                for ln in h.lines:
                    if ln.kind in ("+", "-") and h.old_start + h.old_count == 0:
                        pass
                    if ln.kind == "-":
                        if ln.old_lineno:
                            del_mask[ln.old_lineno] = True
                    elif ln.kind == "+":
                        if ln.new_lineno:
                            add_mask[ln.new_lineno] = True
                    elif ln.kind == " ":
                        # 上下文：成对出现，正常
                        pass

        self._fill_pane(self.left_view, old_lines, del_mask, is_add=False)
        self._fill_pane(self.right_view, new_lines, add_mask, is_add=True)

        added = sum(1 for h in (target.hunks if target else []) for ln in h.lines if ln.is_addition)
        removed = sum(1 for h in (target.hunks if target else []) for ln in h.lines if ln.is_deletion)
        self._header.setText(
            f" {self.path}  ·  {self.rev1 or '工作区'} → {self.rev2 or '工作区'}   "
            f"+{added}/-{removed}")

    def _fill_pane(self, view: QPlainTextEdit, lines: List[str], mask: dict,
                   is_add: bool):
        view.clear()
        doc = view.document()
        add_bg = QColor("#CCFFCC")
        del_bg = QColor("#FFDDDD")
        for i, text in enumerate(lines, start=1):
            cursor = QTextCursor(doc)
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertText(text)
            if i in mask or mask.get(i):
                fmt = QTextCharFormat()
                fmt.setBackground(add_bg if is_add else del_bg)
                # 给该行上色：需选中整行
                block = doc.findBlockByNumber(doc.blockCount() - 1)
                sel = QTextCursor(block)
                sel.select(QTextCursor.SelectionType.LineUnderCursor)
                sel.mergeCharFormat(fmt)
            cursor.insertText("\n")


def _wrap(parent, layout):
    from PySide6.QtWidgets import QWidget
    w = QWidget(parent)
    w.setLayout(layout)
    return w