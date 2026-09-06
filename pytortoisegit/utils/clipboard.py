"""clipboard.py —— 镜像 TortoiseGit 的 Utils/ClipboardHelper。"""

from __future__ import annotations


class ClipboardHelper:
    """访问系统剪贴板文本，不强制依赖 QApplication（懒加载）。"""

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

    def copy_text(self, text: str) -> None:
        _copy_via_qt(text)

    def get_text(self) -> str:
        return _paste_via_qt()


_clipboard_singleton = None


def _app() -> "QApplication | None":  # noqa: F821
    from PySide6.QtWidgets import QApplication
    return QApplication.instance()


def _copy_via_qt(text: str) -> None:
    app = _app()
    if app is None:
        # 无 Qt 运行时直接尝试内置剪贴板工具（仅测试用）
        import subprocess
        if __import__("sys").platform == "win32":
            # PowerShell 将文本放入剪贴板
            import base64
            b64 = base64.b64encode(text.encode("utf-16le")).decode()
            subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"Set-Clipboard -Value ([Text.Encoding]::Unicode.GetString([Convert]::FromBase64String('{b64}')))"],
                check=True, capture_output=True)
        return
    app.clipboard().setText(text)


def _paste_via_qt() -> str:
    app = _app()
    if app is None:
        return ""
    return app.clipboard().text()