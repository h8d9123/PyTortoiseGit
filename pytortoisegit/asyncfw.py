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
from typing import Callable, List, Optional, Set

from PySide6.QtCore import QObject, QThread, Signal


# 正在运行的任务的强引用集合。
#
# 不能把 QThread 挂到 widget 父对象上：调用方习惯写 run_async(..., parent=self)
# 传入对话框，一旦对话框在后台任务还没跑完时被关闭/销毁，Qt 会连带销毁仍在
# 运行的 QThread，进程直接 fail-fast（Windows 上表现为 0xC0000409
# "QThread: Destroyed while thread is still running" 之后的应用崩溃）。
# 这里改为由模块持有引用，线程结束后自动释放；parent 参数保留只为兼容调用方，
# 槽连接的自动断开仍然生效（接收者是 QObject 的绑定方法时由 Qt 负责）。
_live_tasks: Set["_Task"] = set()


def _track(task: "_Task") -> None:
    _live_tasks.add(task)
    task.finished.connect(lambda: _live_tasks.discard(task))


def _guard_callback(parent, callback):
    """把回调包一层"宿主还活着吗"的检查。

    Qt 只能对**绑定方法/QObject 槽**做销毁时自动断连；对 lambda 这类普通
    Python 可调用对象做不到。于是像
        run_async(bg, on_error=lambda m, tb: self.label.setText(m), parent=self)
    这种写法，在对话框已销毁后仍会被调用，去碰已经析构的 C++ 控件——
    轻则抛 "Internal C++ object already deleted"，重则踩到已释放内存。

    这里用 shiboken6.isValid(parent) 在真正回调前挡一道：宿主 C++ 对象没了就
    静默丢弃该次回调。对绑定方法同样适用（行为等价于 Qt 的自动断连）。
    """
    if parent is None or callback is None:
        return callback

    try:
        import shiboken6
    except ImportError:      # 非 PySide 环境不额外拦截
        return callback

    def guarded(*args, **kwargs):
        if not shiboken6.isValid(parent):
            return None
        return callback(*args, **kwargs)

    return guarded


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
        # 见 _live_tasks 的说明：不把 QThread 挂到 widget 父对象上
        task = _Task(func, args=args, kwargs=kwargs, parent=None)
        task.on_done(_guard_callback(self.parent, on_done))
        task.on_error(_guard_callback(self.parent, on_error))
        task.finished.connect(self._check_all)
        _track(task)
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
    """便捷函数。

    parent 不作为 QThread 的父对象（原因见 _live_tasks），但它会被用来给回调
    加一道"宿主是否已销毁"的保护（见 _guard_callback）——所以传 parent 仍然
    是必要的，尤其是 on_done/on_error 写成 lambda 的时候。
    """
    task = _Task(bg_func, args=args, kwargs=kwargs, parent=None)
    task.on_done(_guard_callback(parent, on_done))
    task.on_error(_guard_callback(parent, on_error))
    _track(task)
    task.start()
    return task