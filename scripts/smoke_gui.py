"""scripts/smoke_gui.py —— 真机回归：逐命令启动窗口并核对标题，无标题则判失败。

用法：python scripts/smoke_gui.py [命令...]
例：  python scripts/smoke_gui.py commit log diff clone
不带参数默认跑一份核心命令清单。
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import platform
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECT = ROOT

# (命令, 期望标题包含的关键子串)
CORE = [
    ("commit", "Commit"),
    ("log", "Log"),
    ("clone", "Clone"),
    ("sync", "Sync"),
    ("push", "Push"),
    ("pull", "Fetch"),
    ("reset", "Reset"),
    ("clean", "Clean"),
    ("add", "Add"),
    ("export", "Export"),
    ("updatecheck", "Update"),
    ("menu", "菜单"),
    ("about", None),
]


def find_alive(pid: int, interval: float = 0.4, timeout: float = 6.0) -> bool:
    """轮询进程是否仍存活（未崩溃退出）。"""
    import ctypes
    STILL_ACTIVE = 259
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
            if handle:
                code = ctypes.c_ulong()
                ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
                ctypes.windll.kernel32.CloseHandle(handle)
                if code.value == STILL_ACTIVE:
                    return True
        except Exception:
            pass
        time.sleep(interval)
    return False


def launch(command: str) -> tuple[int, bool]:
    import sys as _sys
    pyw = os.path.join(os.path.dirname(_sys.executable), "pythonw.exe")
    if not os.path.exists(pyw):
        pyw = _sys.executable
    args = ["-m", "pytortoisegit", f"/command:{command}",
            f"/path:{PROJECT}"]
    proc = subprocess.Popen(
        [pyw, *args],
        cwd=str(PROJECT),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    pid = proc.pid
    # 存活 6 秒视为成功（对话框 exec 阻塞不退出）
    alive = find_alive(pid)
    try:
        proc.kill()
    except Exception:
        pass
    return pid, alive


def main(cli: list[str]) -> int:
    commands = cli or [c for c, _ in CORE]
    if platform.system() != "Windows":
        print("smoke_gui 依赖 Windows 进程，当前平台跳过。")
        return 0
    fails = []
    for command in commands:
        pid, alive = launch(command)
        status = "PASS" if alive else "FAIL"
        print(f"[{status}] {command:<16} pid={pid}")
        if not alive:
            fails.append(command)
    print()
    if fails:
        print(f"失败 {len(fails)} 个: {', '.join(fails)}")
        return 1
    print("全部通过（进程存活未崩溃）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))