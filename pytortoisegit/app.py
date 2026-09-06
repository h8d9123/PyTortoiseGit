"""app.py —— 镜像 TortoiseGit 的 TortoiseProc.exe 启动入口。

支持两种运行方式：
    python pytortoisegit/app.py /command:about
    python -m pytortoisegit
    python -m pytortoisegit.app
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

if __package__ in (None, ""):
    # 以普通脚本运行时，把项目根目录加入 sys.path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pytortoisegit.cli import main  # noqa: E402,F401

if __name__ == "__main__":
    raise SystemExit(main())