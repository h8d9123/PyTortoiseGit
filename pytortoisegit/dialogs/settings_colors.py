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
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# This program is derived from and mirrors the TortoiseGit project.

"""settings_colors.py —— 消费端读取设置页 Colors 键的辅助模块。

问题背景：Colors 1–3 设置页只负责把 `Colors/*`、`LogLineWidth`、`LogNodeSize`、
`RevGraphUseLocalForCur`、`UseDarkMode` 等键写入 QSettings，但日志图、修订图、
文件状态色等渲染代码此前全部硬编码默认值，导致“改了颜色看不到变化”。

本模块提供带内存缓存的读取接口，渲染代码按行/按节点调用时只首次读 QSettings；
设置页保存后调用 :func:`invalidate` 清空缓存，下一次绘制立即生效。
"""

from __future__ import annotations

from PySide6.QtGui import QColor

# 每键一个缓存槽；键名 = QSettings 键（含 "Colors/" 前缀）
_cache: dict = {}


def _settings():
    # 延迟导入：settingsdlg 是控件重模块，且测试会 monkeypatch 其 general_settings，
    # 必须在调用时取最新的模块属性绑定。
    from .settingsdlg import general_settings
    return general_settings()


def color(key: str, default: str) -> QColor:
    """读取一个 #RRGGBB 颜色；无效值回退 default。"""
    if key not in _cache:
        raw = str(_settings().value(key, default))
        c = QColor(raw)
        _cache[key] = c if c.isValid() else QColor(default)
    return _cache[key]


def text_value(key: str, default: str) -> str:
    if key not in _cache:
        _cache[key] = str(_settings().value(key, default))
    return _cache[key]


def int_value(key: str, default: int) -> int:
    if key not in _cache:
        raw = _settings().value(key, default)
        try:
            _cache[key] = int(raw)
        except (TypeError, ValueError):
            _cache[key] = default
    return _cache[key]


def bool_value(key: str, default: bool = False) -> bool:
    if key not in _cache:
        raw = _settings().value(key, default)
        if isinstance(raw, bool):
            _cache[key] = raw
        else:
            _cache[key] = str(raw).strip().lower() in ("1", "true", "yes", "on")
    return _cache[key]


def invalidate() -> None:
    """清空缓存：设置页保存颜色后调用，让消费端下次绘制取到新值。"""
    _cache.clear()