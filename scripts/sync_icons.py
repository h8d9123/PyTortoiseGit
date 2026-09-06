"""scripts/sync_icons.py —— 从 TortoiseGit Resources 同步图标到 PyTortoiseGit。

扫描 TortoiseGit-master/src/Resources/*.rc 里的 ICON 定义，
把对应 .ico 复制到 pytortoisegit/res/icons/，并生成 res/icon_map.py。

用法：python scripts/sync_icons.py
"""

from __future__ import annotations

import glob
import os
import re
import shutil
import sys
from pathlib import Path

SRC_ROOT = Path("../TortoiseGit-master/src/Resources")
DST_ROOT = Path("pytortoisegit/res/icons")
MAP_FILE = Path("pytortoisegit/res/icon_map.py")

ICON_RE = re.compile(r'^\s*(\w+)\s+ICON(?:\s+DISCARDABLE)?\s+"([^"]+)"', re.M)

_GPL_HEAD = (
    "# PyTortoiseGit - a Python reimplementation mirroring TortoiseGit.\n"
    "# Copyright (C) 2026  PyTortoiseGit contributors\n"
    "#\n"
    "# This program is free software; you can redistribute it and/or modify it under\n"
    "# the terms of the GNU General Public License as published by the Free Software\n"
    "# Foundation; either version 2 of the License, or (at your option) any later\n"
    "# version.\n"
    "#\n"
    "# This program is distributed in the hope that it will be useful, but WITHOUT\n"
    "# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS\n"
    "# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more\n"
    "# details.\n"
    "#\n"
    "# You should have received a copy of the GNU General Public License along with\n"
    "# this program; if not, write to the Free Software Foundation, Inc., 51\n"
    "# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.\n"
    "#\n"
    "# This program is derived from and mirrors the TortoiseGit project.\n"
)


def collect() -> dict:
    mapping: dict = {}
    for f in glob.glob(str(SRC_ROOT / "*.rc")) + glob.glob(str(SRC_ROOT / "**" / "*.rc"), recursive=True):
        try:
            t = open(f, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        for m in ICON_RE.finditer(t):
            mapping[m.group(1)] = m.group(2).replace("\\", os.sep)
    return mapping


def main() -> int:
    if not SRC_ROOT.is_dir():
        print(f"未找到 {SRC_ROOT}，请在仓库根目录运行。")
        return 1
    mapping = collect()
    os.makedirs(DST_ROOT, exist_ok=True)
    copied = 0
    for rid, rel in sorted(mapping.items()):
        sp = SRC_ROOT / rel
        if not sp.is_file():
            continue
        shutil.copy2(sp, DST_ROOT / os.path.basename(rel))
        copied += 1
    with open(MAP_FILE, "w", encoding="utf-8") as fh:
        fh.write(_GPL_HEAD)
        fh.write('"""icon_map.py —— TortoiseGit 图标资源映射（ID -> 资源文件名）。"""\n\n')
        fh.write("ICON_MAP = {\n")
        for rid, rel in sorted(mapping.items()):
            fh.write(f'    "{rid}": "{os.path.basename(rel)}",\n')
        fh.write("}\n")
    print(f"同步完成：复制 {copied} 个图标，生成 {len(mapping)} 条映射。")
    return 0


if __name__ == "__main__":
    sys.exit(main())