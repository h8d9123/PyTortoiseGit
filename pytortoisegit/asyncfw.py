"""asyncfw.py —— 镜像 TortoiseGit 的 src/AsyncFramework。

把耗时操作放到后台线程执行，避免卡 UI。接口：
    run_async(bg_func, args=(), kwargs=None, on_done=..., on_error=...) -> task
    bg_func 在后台线程执行，on_done/on_error 在主线程回调。
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

import traceback
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from PySide6.QtCore import QObject, QThread, Signal


class _Task(QThread):
    _done = Signal(object)
    _error = Signal(str, str)      # (error_message, traceback_text)

    def __init__(self, func: Callable, args=(), kwargs=None, parent=None):
        super().__init__(parent)
        self._func = func
        self._args = args
        self._kwargs = kwargs or {}
        self._on_done = None
        self._on_error = None

    def run(self):  # 后台线程
        try:
            result = self._func(*self._args, **self._kwargs)
            self._done.emit(result)
        except Exception as exc:  # noqa: BLE001
            self._error.emit(str(exc), traceback.format_exc())

    def on_done(self, callback: Optional[Callable]):
        if callback is not None:
            self._done.connect(callback)
        else:
            self._done.connect(lambda _r: None)

    def on_error(self, callback: Optional[Callable[[str], None]]):
        if callback is not None:
            self._error.connect(callback)
        else:
            self._error.connect(lambda _m, _tb: None)


@dataclass
class TaskManager:
    """管理并发任务，可选全部完成回调。"""
    tasks: List[_Task] = field(default_factory=list)
    parent: Optional[QObject] = None
    _on_finished: Optional[Callable] = None

    def submit(self, func, args=(), kwargs=None, on_done=None, on_error=None) -> _Task:
        task = _Task(func, args=args, kwargs=kwargs, parent=self.parent)
        task.on_done(on_done)
        task.on_error(on_error)
        task.finished.connect(self._check_all)
        self.tasks.append(task)
        task.start()
        return task

    def _check_all(self):
        if self._on_finished and all(t.isFinished() for t in self.tasks):
            self._on_finished()
            self.tasks = []

    def wait_all(self):
        for t in self.tasks:
            t.wait()

    def cancel_all(self):
        for t in self.tasks:
            if t.isRunning():
                t.requestInterruption()

    def on_all_finished(self, callback: Callable):
        self._on_finished = callback


def run_async(bg_func, args=(), kwargs=None, on_done=None, on_error=None, parent=None) -> _Task:
    """便捷函数。"""
    task = _Task(bg_func, args=args, kwargs=kwargs, parent=parent)
    task.on_done(on_done)
    task.on_error(on_error)
    task.start()
    return task