"""progress.py —— 运行命令并显示进度的对话框（镜像 TortoiseGit 进度对话框）。"""

from __future__ import annotations

import queue
import sys
import threading
from typing import Callable, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
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
        self.setWindowTitle(title or tr("progress_title", "Git command progress"))
        self.resize(560, 360)
        self._cancelled = False
        self._cancellable = cancellable
        self._done = False
        self._exit_code = 0
        self._q: "queue.Queue" = queue.Queue()
        self._worker_thread: Optional[threading.Thread] = None
        self._poll: QTimer | None = None
        self._on_finish: Optional[Callable[[bool], None]] = None
        self._morphed = False
        self._build_ui()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._drain)

    def _build_ui(self):
        # 对齐 IDD_GITPROGRESS：状态行、进度条、日志、Close(完成前禁用)/Abort
        layout = QVBoxLayout(self)
        self._label = QLabel(tr("progress_wait", "Please wait…"), self)
        layout.addWidget(self._label)

        self.progress = QProgressBar(self)
        self.progress.setRange(0, 0)
        layout.addWidget(self.progress)

        self.output = QPlainTextEdit(self)
        self.output.setReadOnly(True)
        self.output.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self.output, 1)

        buttons = QHBoxLayout()
        self._post_box = QHBoxLayout()
        buttons.addLayout(self._post_box)
        buttons.addStretch(1)
        self._btn_cancel = QPushButton(tr("abort", "Abort"), self)
        self._btn_cancel.clicked.connect(self.cancel)
        if not self._cancellable:
            self._btn_cancel.hide()
        self._btn_close = QPushButton(tr("close"), self)
        self._btn_close.setEnabled(False)
        self._btn_close.setDefault(True)
        self._btn_close.clicked.connect(self.accept)
        buttons.addWidget(self._btn_cancel)
        buttons.addWidget(self._btn_close)
        layout.addLayout(buttons)

    def set_label(self, text: str):
        self._label.setText(text)

    def log(self, text: str):
        if not text:
            return
        self.output.appendPlainText(text.rstrip("\n"))

    def log_async(self, text: str):
        """后台线程写日志（经队列回到 UI 线程）。"""
        self._q.put(text)

    def run_git(self, runner, *args: str):
        """跑一条 git 命令：先写命令行，再收输出，结束时标 Success / 退出码。"""
        shown = "git.exe " + " ".join(args)
        self.log(shown + "\n")
        self.set_label(tr("progress_wait", "Please wait…"))

        def _bg():
            r = runner.run_interactive(*args)
            parts = []
            if r.stdout and r.stdout.strip():
                parts.append(r.stdout.rstrip())
            if r.stderr and r.stderr.strip():
                parts.append(r.stderr.rstrip())
            if parts:
                self.log_async("\n".join(parts))
            return r.returncode == 0, r.returncode

        self.run(_bg)

    def run(self, fn: Callable):
        """在后台线程执行 fn()；返回 True 或 (ok, exit_code)。完成后调用 _on_finish。"""
        self._done = False
        # 恢复“中止”按钮形态（可能已被 _finish 改写成“关闭”）
        self._btn_close.show()
        self._btn_close.setEnabled(False)
        if self._cancellable and self._morphed:
            self._btn_cancel.setText(tr("abort", "Abort"))
            self._btn_cancel.clicked.disconnect(self.accept)
            self._btn_cancel.clicked.connect(self.cancel)
            self._morphed = False
        self.progress.setRange(0, 0)
        self._worker_thread = threading.Thread(
            target=self._runner, args=(fn,), daemon=True)
        self._worker_thread.start()
        self._timer.start(50)

    def _runner(self, fn: Callable):
        try:
            result = fn()
            if isinstance(result, tuple):
                ok, code = bool(result[0]), int(result[1])
            else:
                ok = bool(result)
                code = 0 if ok else 1
            self._q.put(("\x00done", ok, code))
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
                code = int(item[2]) if len(item) > 2 else 0
                self._finish(bool(item[1]), code)
            elif isinstance(item, tuple) and item and item[0] == "\x00error":
                self.log(str(item[1]))
                self._finish(False, 1)
            else:
                self.log(str(item))

    def _finish(self, ok: bool, code: int = 0):
        if self._done:
            return
        self._done = True
        self._exit_code = code
        if self._timer.isActive():
            self._timer.stop()
        self.progress.setRange(0, 100)
        self.progress.setValue(100)
        if ok:
            msg = tr("progress_success", "Success")
            self._label.setText(msg)
            self.log("\n" + msg)
        else:
            msg = tr("progress_unclean", "git did not exit cleanly (exit code {})").format(code)
            self._label.setText(msg)
            self.log("\n" + msg)
            self.progress.setStyleSheet(
                "QProgressBar::chunk { background-color: #c00000; }")
        # 对齐用户预期：操作结束后“中止”按钮就地变成“关闭”
        close_btn = self._btn_close
        if self._cancellable and not self._morphed:
            self._btn_close.hide()
            self._btn_cancel.setText(tr("close"))
            self._btn_cancel.clicked.disconnect(self.cancel)
            self._btn_cancel.clicked.connect(self.accept)
            self._morphed = True
        if self._cancellable:
            self._btn_cancel.setEnabled(True)
            close_btn = self._btn_cancel
        close_btn.setEnabled(True)
        close_btn.setDefault(True)
        close_btn.setFocus()
        if self._on_finish:
            self._on_finish(ok)

    def add_post_action(self, label: str, callback: Callable[[], None]):
        """对齐 ProgressDlg 失败后的 post-cmd（Pull / Fetch / 再 Push）。"""
        btn = QPushButton(label, self)

        def _go():
            self.accept()
            callback()

        btn.clicked.connect(_go)
        self._post_box.addWidget(btn)

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