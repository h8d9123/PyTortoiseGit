"""verify_dist.py —— 验证打包产物（dist/PyTortoiseGit）是否可用。

打包 bug 常常只在运行冻结产物时才暴露（漏数据文件、缺 DLL、黑控制台窗口、
hiddenimport 缺失），源码测试覆盖不到。本脚本直接在 dist 上做冒烟：

  1. 目录/关键文件：可执行文件、_internal、res 资源文件集（源码 vs 打包逐一对齐）、
     关键 Qt 运行库；
  2. 体积基线：超过阈值判失败，防插件/依赖回涨；
  3. 逐命令启动 exe：进程存活 + 出现可见窗口 + 期间无可见控制台窗口 +
     日志无新增 ERROR/Traceback。

用法：
    python scripts/verify_dist.py                 # 默认命令清单
    python scripts/verify_dist.py --commands about commit log
    python scripts/verify_dist.py --dist dist/PyTortoiseGit --max-mb 120
    python scripts/verify_dist.py --no-launch     # 只查文件与体积

退出码：0 全部通过；1 有失败项。
"""

from __future__ import annotations

import argparse
import ctypes
import os
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_RES = ROOT / "pytortoisegit" / "res"

# 各命令启动后应出现的窗口标题关键子串（None 表示只要求进程存活）
DEFAULT_COMMANDS: list[tuple[str, str | None]] = [
    ("about", None),
    ("commit", "Commit"),
    ("log", "Log"),
    ("diff", "Working Tree"),
    ("settings", "设置"),
    ("reflog", "reflog"),
    ("clone", "clone"),
    ("push", "Push"),
    ("pull", "拉取"),
    ("merge", "合并"),
]

# 平台相关：Windows 产物为 .exe + Qt6Xxx.dll，Linux 为无扩展名可执行 + libQt6Xxx.so.6。
_IS_WINDOWS = os.name == "nt"
EXE_NAME = "PyTortoiseGit.exe" if _IS_WINDOWS else "PyTortoiseGit"
REQUIRED_QT_LIBS = (
    ("PySide6/Qt6Core.dll", "PySide6/Qt6Gui.dll", "PySide6/Qt6Widgets.dll")
    if _IS_WINDOWS else
    ("PySide6/Qt/lib/libQt6Core.so.6",
     "PySide6/Qt/lib/libQt6Gui.so.6",
     "PySide6/Qt/lib/libQt6Widgets.so.6")
)
PYTHON_RUNTIME_GLOB = "python3*.dll" if _IS_WINDOWS else "libpython3*.so*"
SKIP_SUFFIXES = {".py", ".pyc"}


# ---------------------------------------------------------------------------
# 文件检查
# ---------------------------------------------------------------------------
def _packaged_res(dist: Path) -> Path:
    return dist / "_internal" / "pytortoisegit" / "res"


def check_files(dist: Path) -> list[str]:
    problems: list[str] = []
    exe = dist / EXE_NAME
    if not exe.is_file():
        problems.append(f"缺少可执行文件：{exe}")
    internal = dist / "_internal"
    if not internal.is_dir():
        problems.append(f"缺少 _internal 目录：{internal}")
        return problems

    # 运行时按路径加载的数据文件必须与源码 res 一一对应
    packed_res = _packaged_res(dist)
    if SRC_RES.is_dir():
        for src in sorted(SRC_RES.rglob("*")):
            if not src.is_file() or src.suffix in SKIP_SUFFIXES:
                continue
            if "__pycache__" in src.parts:
                continue
            rel = src.relative_to(SRC_RES)
            if not (packed_res / rel).is_file():
                problems.append(f"未打包资源：pytortoisegit/res/{rel.as_posix()}")

    # 关键 Qt 运行库
    for rel in REQUIRED_QT_LIBS:
        if not (internal / rel).is_file():
            problems.append(f"缺少 Qt 运行库：{rel}")
    if not any(internal.glob(PYTHON_RUNTIME_GLOB)):
        problems.append(f"缺少 python 运行库：_internal/{PYTHON_RUNTIME_GLOB}")
    return problems


def dir_size_mb(path: Path) -> float:
    """按 inode 去重统计体积，避免 PyInstaller 的符号链接/硬链接被重复计算。"""
    seen: set[tuple[int, int]] = set()
    total = 0
    for f in path.rglob("*"):
        if not f.is_file():
            continue
        st = f.stat()
        key = (st.st_dev, st.st_ino)
        if key in seen:
            continue
        seen.add(key)
        total += st.st_size
    return total / (1024 * 1024)


# ---------------------------------------------------------------------------
# Windows 窗口/进程探测（ctypes，无第三方依赖）
# ---------------------------------------------------------------------------
if _IS_WINDOWS:
    _user32 = ctypes.windll.user32
    _kernel32 = ctypes.windll.kernel32
    _WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    _STILL_ACTIVE = 259
    _PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def _is_alive(pid: int) -> bool:
    if not _IS_WINDOWS:
        return False
    handle = _kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return False
    code = wintypes.DWORD()
    ok = _kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
    _kernel32.CloseHandle(handle)
    return bool(ok) and code.value == _STILL_ACTIVE


def _scan_windows(pid: int) -> tuple[bool, int]:
    """扫描指定进程的顶层可见窗口，返回 (是否有带标题窗口, 可见控制台窗口数)。"""
    if not _IS_WINDOWS:
        return (False, 0)
    found = {"window": False, "console": 0}

    def _cb(hwnd, _lparam):
        if not _user32.IsWindowVisible(hwnd):
            return True
        wpid = wintypes.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
        if wpid.value != pid:
            return True
        buf = ctypes.create_unicode_buffer(256)
        _user32.GetClassNameW(hwnd, buf, 256)
        if buf.value == "ConsoleWindowClass":
            found["console"] += 1
        elif _user32.GetWindowTextLengthW(hwnd) > 0:
            found["window"] = True
        return True

    _user32.EnumWindows(_WNDENUMPROC(_cb), 0)
    return (found["window"], found["console"])


# ---------------------------------------------------------------------------
# 日志
# ---------------------------------------------------------------------------
def _log_path() -> Path:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return Path(base) / "PyTortoiseGit" / "pytortoisegit.log"


def _log_offset() -> int:
    path = _log_path()
    return path.stat().st_size if path.exists() else 0


def _new_log_errors(offset: int) -> str:
    path = _log_path()
    if not path.exists():
        return ""
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        fh.seek(offset)
        text = fh.read()
    bad = [ln for ln in text.splitlines()
           if "ERROR" in ln or "Traceback" in ln or "FileNotFoundError" in ln]
    return "\n".join(bad)


# ---------------------------------------------------------------------------
# 启动冒烟
# ---------------------------------------------------------------------------
class Result:
    def __init__(self, command: str):
        self.command = command
        self.alive = False
        self.window = False
        self.consoles = 0
        self.errors = ""
        self.title = ""

    @property
    def ok(self) -> bool:
        return self.alive and self.window and self.consoles == 0 and not self.errors


def _child_env() -> dict:
    """启动被测 exe 的环境：去掉 QT_QPA_PLATFORM，强制走真实窗口平台。

    CI/测试常在父进程设 offscreen，若被继承则冻结产物也是无头运行、永远
    探测不到可见窗口。
    """
    env = dict(os.environ)
    env.pop("QT_QPA_PLATFORM", None)
    return env


def launch_and_probe(exe: Path, command: str, repo: Path,
                     wait: float = 7.0) -> Result:
    res = Result(command)
    offset = _log_offset()
    args = [str(exe)]
    if command != "menu":
        args += [f"/command:{command}"]
    if repo:
        args += [f"/path:{repo}"]
    proc = subprocess.Popen(args, cwd=str(exe.parent),
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            env=_child_env())
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        alive = _is_alive(proc.pid)
        has_win, consoles = _scan_windows(proc.pid)
        res.alive = alive
        res.window = res.window or has_win
        res.consoles = max(res.consoles, consoles)
        if not alive:
            break
        time.sleep(0.25)
    try:
        proc.kill()
    except Exception:  # noqa: BLE001
        pass
    proc.wait(timeout=10)
    res.errors = _new_log_errors(offset)
    return res


# ---------------------------------------------------------------------------
def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="验证 PyTortoiseGit 打包产物")
    parser.add_argument("--dist", type=Path,
                        default=ROOT / "dist" / "PyTortoiseGit",
                        help="打包产物目录")
    parser.add_argument("--repo", type=Path, default=ROOT,
                        help="探测时传给 /path 的仓库路径")
    parser.add_argument("--commands", nargs="*", default=None,
                        help="要冒烟的命令（默认内置清单）")
    parser.add_argument("--wait", type=float, default=7.0,
                        help="每条命令的观察时长（秒）")
    parser.add_argument("--max-mb", type=float, default=150.0,
                        help="体积上限（MB），超过判失败")
    parser.add_argument("--no-launch", action="store_true",
                        help="只做文件与体积检查，不启动程序")
    args = parser.parse_args(argv)

    dist = args.dist.resolve()
    if not dist.is_dir():
        print(f"FAIL 打包目录不存在：{dist}（先运行 python packaging/build.py）")
        return 1

    failures: list[str] = []

    print("== 文件检查 ==")
    for problem in check_files(dist):
        print("  FAIL", problem)
        failures.append(problem)
    if not failures:
        print("  OK 关键文件与资源齐全")

    size = dir_size_mb(dist)
    print(f"== 体积：{size:.1f} MB（上限 {args.max_mb:.0f} MB）==")
    if size > args.max_mb:
        msg = f"体积 {size:.1f} MB 超过上限 {args.max_mb:.0f} MB"
        print("  FAIL", msg)
        failures.append(msg)

    if args.no_launch:
        print("\n结果：" + ("全部通过" if not failures else f"失败 {len(failures)} 项"))
        return 1 if failures else 0

    if not _IS_WINDOWS:
        print("非 Windows 平台：跳过启动冒烟。")
        return 1 if failures else 0

    commands = args.commands
    if commands:
        wanted = {c: None for c in commands}
        commands = [(c, wanted[c]) for c in commands]
    else:
        commands = DEFAULT_COMMANDS

    print("== 启动冒烟 ==")
    exe = dist / EXE_NAME
    for command, _hint in commands:
        res = launch_and_probe(exe, command, args.repo, args.wait)
        status = "PASS" if res.ok else "FAIL"
        print(f"  [{status}] {command:<10} alive={res.alive} "
              f"window={res.window} consoles={res.consoles}")
        if res.errors:
            print("        日志异常：", res.errors.replace("\n", "\n        "))
        if not res.ok:
            failures.append(command)

    print()
    if failures:
        print(f"失败 {len(failures)} 项：{', '.join(failures)}")
        return 1
    print("全部通过：资源齐全、体积达标、命令可启动、无黑控制台窗口、日志无异常。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
