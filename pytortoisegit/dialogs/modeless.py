"""modeless.py —— 非模态“工具窗口”打开助手。

对齐 TortoiseGit 的工具窗口（Log / FileDiff / RevGraph / RepoBrowser /
Blame / StatGraph / PatchView）：用 show() 打开而不是 exec()，父窗口不被阻塞。
需要持有引用避免被 GC，并在关闭/销毁后释放。
"""

from __future__ import annotations

from typing import List

_open_windows: List[object] = []


def _is_valid(dlg) -> bool:
    """判断底层 C++ 对象是否仍存活（被父窗口销毁后为 False）。"""
    try:
        import shiboken6
        return bool(shiboken6.Shiboken.isValid(dlg))
    except Exception:  # noqa: BLE001
        return True


def show_modeless(dlg):
    """非模态打开对话框并保住引用（防 GC），关闭/销毁后自动释放。"""
    _open_windows.append(dlg)
    for attr in ("finished", "destroyed"):
        sig = getattr(dlg, attr, None)
        if sig is None:
            continue
        try:
            sig.connect(lambda *_, _d=dlg: _release(_d))
        except Exception:  # noqa: BLE001
            continue
    dlg.show()
    for meth in ("raise_", "activateWindow"):
        fn = getattr(dlg, meth, None)
        if fn is not None:
            try:
                fn()
            except Exception:  # noqa: BLE001
                pass
    return dlg


def _release(dlg) -> None:
    """按身份移除引用，避免对已销毁对象做比较。"""
    for i, item in enumerate(_open_windows):
        if item is dlg:
            del _open_windows[i]
            return


def close_all() -> None:
    """关闭并释放所有工具窗口（测试收尾用）。"""
    for dlg in list(_open_windows):
        if not _is_valid(dlg):
            continue
        try:
            dlg.close()
        except Exception:  # noqa: BLE001
            pass
    _open_windows.clear()


def open_windows() -> List[object]:
    """当前打开的工具窗口（测试用）。"""
    return list(_open_windows)
