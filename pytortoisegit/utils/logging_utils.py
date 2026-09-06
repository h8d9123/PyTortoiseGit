"""logging_utils.py —— 全局异常钩子与日志记录。

未捕获异常统一写入日志文件，并在 GUI 模式下弹出错误对话框。
日志位于 %APPDATA%/PyTortoiseGit/pytortoisegit.log（无 GUI 时仅写文件）。
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

import logging
import os
import sys
import threading
import traceback


def _log_dir() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    path = os.path.join(base, "PyTortoiseGit")
    os.makedirs(path, exist_ok=True)
    return path


def get_logger(name: str = "pytortoisegit") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(
        os.path.join(_log_dir(), "pytortoisegit.log"), encoding="utf-8")
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def _show_error(message: str):
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
        app = QApplication.instance()
        if app is None:
            return
        QMessageBox.critical(None, "错误", message)
    except Exception:  # noqa: BLE001
        pass


def install_excepthooks(show_dialog: bool = True) -> None:
    """安装 sys.excepthook 与线程异常钩子；可重复调用（幂等）。"""
    logger = get_logger()

    def _handle(exc_type, exc, tb, thread_label: str = ""):
        detail = "".join(traceback.format_exception(exc_type, exc, tb))
        logger.error("%s未捕获异常:\n%s", thread_label, detail)
        if show_dialog:
            _show_error(f"{thread_label}发生未捕获异常：\n{exc}\n\n"
                        f"详情已写入日志文件。")

    def _syshook(exc_type, exc, tb):
        _handle(exc_type, exc, tb)

    def _threadhook(args):
        _handle(args.exc_type, args.exc_value, args.exc_traceback,
                thread_label=f"[线程 {args.thread.name}] ")

    sys.excepthook = _syshook
    threading.excepthook = _threadhook