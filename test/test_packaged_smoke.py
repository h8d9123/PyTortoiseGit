"""打包产物冒烟测试（opt-in）。

源码测试覆盖不到冻结产物的问题（漏数据文件、缺 DLL、黑控制台窗口、
hiddenimport 缺失），这里直接对 dist/ 跑 scripts/verify_dist.py。

默认跳过；启用方式：
    $env:PYTG_PACKAGED=1; python packaging/build.py --clean; pytest test/test_packaged_smoke.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist" / "PyTortoiseGit"
SCRIPT = ROOT / "scripts" / "verify_dist.py"


def _run(*args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", cwd=str(ROOT), env=env)


pytestmark = [
    pytest.mark.skipif(os.name != "nt", reason="打包冒烟仅支持 Windows"),
    pytest.mark.skipif(os.environ.get("PYTG_PACKAGED") != "1",
                       reason="设置 PYTG_PACKAGED=1 才运行打包产物冒烟"),
    pytest.mark.skipif(not (DIST / "PyTortoiseGit.exe").is_file(),
                       reason="dist 产物不存在，请先运行 python packaging/build.py"),
]


def test_dist_files_and_resources():
    """资源文件集、关键 Qt DLL 与体积基线。"""
    result = _run("--no-launch")
    assert result.returncode == 0, result.stdout + result.stderr


def test_dist_launches_about():
    """冻结产物能启动并出现可见窗口，且无黑控制台窗口、日志无异常。"""
    result = _run("--commands", "about")
    assert result.returncode == 0, result.stdout + result.stderr
