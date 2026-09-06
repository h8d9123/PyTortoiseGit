#!/usr/bin/env python
"""packaging/build.py —— 一键构建 PyTortoiseGit 可分发包。

用法：
    python packaging/build.py            # 构建 onedir 版本（dist/PyTortoiseGit/）
    python packaging/build.py --clean    # 先清理 build/dist 再构建

依赖：pip install pyinstaller
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SPEC = ROOT / "packaging" / "PyTortoiseGit.spec"
DIST = ROOT / "dist"
BUILD = ROOT / "build"


def main() -> int:
    args = set(sys.argv[1:])
    if "--clean" in args:
        for p in (DIST, BUILD):
            if p.exists():
                shutil.rmtree(p, ignore_errors=True)

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("缺少 pyinstaller，请先执行：pip install pyinstaller")
        return 1

    cmd = [sys.executable, "-m", "PyInstaller", str(SPEC), "--noconfirm"]
    print("运行：" + " ".join(cmd))
    return subprocess.call(cmd, cwd=str(ROOT))


if __name__ == "__main__":
    sys.exit(main())