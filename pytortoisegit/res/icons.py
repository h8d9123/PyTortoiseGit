"""icons.py —— 镜像 TortoiseGit 的 Resources。加载 TortoiseGit 真实图标资源。

TortoiseGit 的图标已经由 scripts/sync_icons.py 复制到 res/icons/。
本模块按 ICON_MAP（ID -> 文件名）加载，backport 到 Qt QIcon。

注：Qt Windows 的 qico 插件一次加载多帧 .ico 会崩溃（stack buffer overflow），
故用 QImageReader 读单帧 -> QPixmap -> QIcon，避免 QIcon(ico) bug。
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

import os
import sys
from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon, QImageReader, QPixmap

_ICON_DIR = Path(__file__).resolve().parent / "icons"
from .icon_map import ICON_MAP  # noqa: E402

# 语义名 -> ICON_MAP ID 的别名（便于按用途取图标）
_ALIASES = {
    "app": "IDR_MAINFRAME",
    "tortoise": "IDR_MAINFRAME",
    "git": "IDI_GITFOLDER",
    "commit": "IDI_COMMIT_BKG",
    "log": "IDI_DIALOGS",
    "diff": "IDI_SWITCHLEFTRIGHT",
    "branch": "IDI_GITREMOTE",
    "settings": "IDI_GENERAL",
    "general": "IDI_GENERAL",
    "reflog": "IDI_GITFOLDER",
    "stash": "IDI_SAVE",
    "rebuild_icon": "IDI_ICONSET",
    "cancel": "IDI_CANCELNORMAL",
    "cancel_pressed": "IDI_CANCELPRESSED",
    "filter": "IDI_FILTEREDIT",
    "refresh": "IDI_REFRESH",
    "save": "IDI_SAVE",
    "saveas": "IDI_SAVEAS",
    "open": "IDI_OPEN",
    "error": "IDI_ACTIONERROR",
}

# 单帧读取缓存
_icon_cache: dict = {}


def _load_ico(path: Path) -> QIcon | None:
    try:
        reader = QImageReader(str(path))
        reader.setAutoTransform(False)
        img = reader.read()
        if img is not None and not img.isNull():
            pix = QPixmap.fromImage(img)
            return QIcon(pix)
    except Exception:  # noqa: BLE001
        return None
    return None


def _resolve_resource_id(name: str) -> str | None:
    """把名字解析成 ICON_MAP 里的资源 ID。"""
    if name in ICON_MAP:
        return name
    if name in _ALIASES:
        return _ALIASES[name]
    naive = "IDI_" + name.upper()
    if naive in ICON_MAP:
        return naive
    # 尝试直接按文件名 basename 匹配（不含 .ico）
    for rid, fn in ICON_MAP.items():
        if os.path.splitext(fn)[0].lower() == name.lower():
            return rid
    return None


def icon(name: str, size: int | None = None) -> QIcon:
    """按 ID / 语义名取 TortoiseGit 图标。"""
    rid = _resolve_resource_id(name)
    if rid is None:
        # 回退：语义主题
        return _theme_fallback(name, size)
    fn = ICON_MAP.get(rid)
    if not fn:
        return _theme_fallback(name, size)
    path = _ICON_DIR / fn
    if path not in _icon_cache:
        _icon_cache[path] = _load_ico(path) or QIcon()
    qicon = _icon_cache[path]
    if size is not None and not qicon.isNull():
        return QIcon(qicon.pixmap(QSize(size, size)))
    return qicon


# ---- 主题回退（原逻辑） ----
_THEME_FALLBACKS = {
    "git.commit": "git-commit",
    "git.log": "git-log",
    "git.branch": "git-branch",
    "git.diff": "text-x-diff",
}


def _theme_candidates(name: str):
    yield name
    if name in _THEME_FALLBACKS:
        yield _THEME_FALLBACKS[name]


def _theme_fallback(name: str, size: int | None = None) -> QIcon:
    from PySide6.QtWidgets import QStyle, QApplication
    app = QApplication.instance()
    if app is None:
        return QIcon()
    for cand in _theme_candidates(name):
        if QIcon.hasThemeIcon(cand):
            return QIcon.fromTheme(cand)
    mapping = {
        "git.commit": QStyle.StandardPixmap.SP_DialogApplyButton,
        "git.log": QStyle.StandardPixmap.SP_FileDialogContentsView,
        "git.diff": QStyle.StandardPixmap.SP_FileDialogDetailedView,
        "git.branch": QStyle.StandardPixmap.SP_DirLinkIcon,
    }
    std = mapping.get(name)
    if std is not None:
        return app.style().standardIcon(std)
    return QIcon()


def app_icon(size: int = 256) -> QIcon:
    """TortoiseGit 主应用图标。"""
    return icon("IDR_MAINFRAME", size=None) or icon("tortoise")


def pixmap_from_icon(qicon: QIcon, size: int = 16):  # noqa: F821
    return qicon.pixmap(QSize(size, size))