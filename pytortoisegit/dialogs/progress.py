"""progress.py —— 运行命令并显示进度的对话框（镜像 TortoiseGit 进度对话框）。"""

from __future__ import annotations

import queue
import sys
import threading
from typing import Callable, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from ..res.strings import tr


class ProgressDialog(QDialog):
    """后台执行函数，把输出追加到文本框。"""

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

    def __init__(self, title: str = "", parent=None, cancellable: bool = True):
        super().__init__(parent)
        self.setWindowTitle(title or tr("progress"))
        self.resize(560, 360)
        self._cancelled = False
        self._cancellable = cancellable
        self._q: "queue.Queue[str]" = queue.Queue()
        self._worker_thread: Optional[threading.Thread] = None
        self._poll: QTimer | None = None
        self._on_finish: Optional[Callable[[bool], None]] = None
        self._build_ui()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._drain)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        self._label = QLabel(self)
        layout.addWidget(self._label)

        self.output = QPlainTextEdit(self)
        self.output.setReadOnly(True)
        self.output.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self.output, 1)

        self.progress = QProgressBar(self)
        self.progress.setRange(0, 0)   # 不确定进度
        layout.addWidget(self.progress)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self._btn_cancel = QPushButton(tr("cancel"), self)
        self._btn_cancel.clicked.connect(self.cancel)
        if not self._cancellable:
            self._btn_cancel.hide()
        buttons.addWidget(self._btn_cancel)
        buttons.addWidget(
            QPushButton(tr("close"), self, clicked=lambda: self.reject())
        )
        layout.addLayout(buttons)

    def set_label(self, text: str):
        self._label.setText(text)

    def log(self, text: str):
        self.output.appendPlainText(text)

    def run(self, fn: Callable[[], bool]):
        """在后台线程执行 fn()；返回 True 表示成功。完成后调用 _on_finish。"""
        self._worker_thread = threading.Thread(
            target=self._runner, args=(fn,), daemon=True)
        self._worker_thread.start()
        self._timer.start(50)

    def _runner(self, fn: Callable[[], bool]):
        try:
            ok = fn()
            self._q.put(("\x00done", ok))
        except Exception as exc:  # noqa: BLE001
            import traceback
            self._q.put(("\x00error", f"{exc}\n{traceback.format_exc()}"))

    def _drain(self):
        messages = []
        while True:
            try:
                messages.append(self._q.get_nowait())
            except queue.Empty:
                break
        for item in messages:
            if isinstance(item, tuple) and item and item[0] == "\x00done":
                self._finish(bool(item[1]))
            elif isinstance(item, tuple) and item and item[0] == "\x00error":
                self.log(str(item[1]))
                self._finish(False)
            else:
                self.log(str(item))

    def _finish(self, ok: bool):
        if self._timer.isActive():
            self._timer.stop()
        self.progress.setRange(0, 100)
        self.progress.setValue(100 if ok else 0)
        if self._on_finish:
            self._on_finish(ok)

    def on_finish(self, callback: Callable[[bool], None]):
        self._on_finish = callback

    def cancel(self):
        self._cancelled = True
        self._btn_cancel.setEnabled(False)


class CommandOutputWriter:
    """把后台命令的输出流式写入 ProgressDialog。"""

    def __init__(self, dlg: ProgressDialog):
        self.dlg = dlg

    def write(self, data: str):
        self.dlg.log(data.rstrip("\n") if data.endswith("\n") else data)

    def flush(self):
        pass