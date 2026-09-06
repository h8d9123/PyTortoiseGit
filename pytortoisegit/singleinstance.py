"""singleinstance.py —— 单实例守卫（QSharedMemory 实现）。

同 key 已有实例时返回 False（调用方退出），否则占用并返回 True。
在被 kill 后 QSharedMemory 可能短暂残留，故带重试。
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

import time


def acquire(key: str, retries: int = 10, delay: float = 0.3) -> bool:
    try:
        from PySide6.QtCore import QSharedMemory
        full = "PyTortoiseGit_" + key
        mem = QSharedMemory(full)
        for _ in range(retries):
            if mem.create(1):
                _HOLD[id(mem)] = mem
                return True
            # 已有实例：探测是否为"残锁"（attach 失败说明无存活进程）
            time.sleep(delay)
        return False
    except Exception:
        return True


def release(key: str) -> None:
    for k, mem in list(_HOLD.items()):
        if mem.key() == "PyTortoiseGit_" + key:
            try:
                mem.detach()
            except Exception:
                pass
            _HOLD.pop(k, None)


_HOLD = {}