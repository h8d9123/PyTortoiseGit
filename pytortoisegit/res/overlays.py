"""overlays.py —— 版本控制状态覆盖图标（跨平台）。

原版 TortoiseGit 在 Windows 上通过 Shell 图标覆盖（TortoiseOverlays DLL）
显示绿勾/红改等；Linux/macOS 没有这套机制。本模块内置这套覆盖图标，并由
主窗口自行合成到文件基础图标上，从而在各平台都能显示状态覆盖。

注意：`compose()` 会创建 QPixmap，只能在 GUI 线程调用；`overlay_icon()`
首次加载也会创建 QPixmap，因此同样应在 GUI 线程预热（见 _GitIconProvider）。
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon, QImageReader, QPainter, QPixmap

_OVERLAY_DIR = Path(__file__).resolve().parent / "overlay"

OVERLAY_MAP = {
    "normal": "NormalIcon.ico",
    "modified": "ModifiedIcon.ico",
    "added": "AddedIcon.ico",
    "conflicted": "ConflictIcon.ico",
    "deleted": "DeletedIcon.ico",
    "ignored": "IgnoredIcon.ico",
    "unversioned": "UnversionedIcon.ico",
    "readonly": "ReadOnlyIcon.ico",
    "locked": "LockedIcon.ico",
}

# 目录聚合时取“更严重”的状态（对齐 TortoiseGit 的覆盖优先级）
PRIORITY = {
    "normal": 0, "ignored": 1, "unversioned": 2, "added": 3,
    "deleted": 4, "modified": 5, "conflicted": 6,
}

_icon_cache: dict = {}


def worse(a: str | None, b: str | None) -> str | None:
    """返回优先级更高的状态。"""
    if a is None:
        return b
    if b is None:
        return a
    return a if PRIORITY.get(a, 0) >= PRIORITY.get(b, 0) else b


def overlay_icon(status: str) -> QIcon | None:
    """取状态覆盖图标（GUI 线程；首次会创建 QPixmap 并缓存）。

    加载 .ico 的**全部帧**并加入 QIcon，使 Qt 在按目标尺寸取图时选用最接近的
    原生帧。覆盖图标的覆盖图形只占每帧左下角一部分：16x16 帧约 8x8、48x48 帧
    约 16x16。若只读第 0 帧（通常为 48x48）再缩到 16x16，覆盖图形会缩到约
    5x5，显得过小。
    """
    if status not in _icon_cache:
        fn = OVERLAY_MAP.get(status)
        ic: QIcon | None = None
        if fn:
            path = _OVERLAY_DIR / fn
            if path.is_file():
                reader = QImageReader(str(path))
                reader.setAutoTransform(False)
                count = reader.imageCount()
                if count <= 0:
                    count = 1
                icon = QIcon()
                added = False
                for i in range(count):
                    reader.jumpToImage(i)
                    img = reader.read()
                    if img is not None and not img.isNull():
                        icon.addPixmap(QPixmap.fromImage(img))
                        added = True
                ic = icon if added else None
        _icon_cache[status] = ic
    return _icon_cache[status]


def compose(base: QIcon | None, status: str | None, size: int = 16) -> QIcon | None:
    """把状态覆盖图标合成到基础图标左下角（GUI 线程）。"""
    if status in (None, "normal"):
        # normal 也画绿勾（与原版一致），仅当没有基础图标时退回
        pass
    ov = overlay_icon(status) if status else None
    if base is None or base.isNull():
        return base
    if ov is None or ov.isNull():
        return base
    pm = base.pixmap(QSize(size, size))
    if pm.isNull():
        return base
    ovpm = ov.pixmap(QSize(size, size))
    if ovpm.isNull():
        return base
    painter = QPainter(pm)
    painter.drawPixmap(0, 0, ovpm)
    painter.end()
    return QIcon(pm)
