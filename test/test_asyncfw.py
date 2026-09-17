"""asyncfw 专项测试：后台任务的父对象生命周期。

回归背景：旧实现把后台 QThread 挂到调用方传入的 parent(widget) 上，一旦对话框
在任务还没跑完时被关闭/销毁，Qt 会连带销毁仍在运行的 QThread，进程直接
fail-fast（Windows 上 0xC0000409，日志为
"QThread: Destroyed while thread is still running"）。该问题影响所有使用
run_async(..., parent=self) 的对话框（日志、提交、差异、仓库浏览器、修订图等）。
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_run_async_survives_parent_destruction(qapp):
    """任务运行中销毁 parent，不能连带销毁 QThread。

    若退回旧行为，整个 pytest 进程会崩掉——这正是它能防住回归的原因。
    """
    import time

    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QWidget
    from pytortoisegit.asyncfw import _live_tasks, run_async

    seen = {}

    def slow():
        time.sleep(0.6)
        return 42

    parent_widget = QWidget()
    run_async(slow, on_done=lambda r: seen.setdefault("r", r),
              parent=parent_widget)
    parent_widget.deleteLater()

    loop = QEventLoop()
    QTimer.singleShot(2500, loop.quit)
    loop.exec()

    assert seen.get("r") == 42, "任务应正常跑完并回调"
    assert not _live_tasks, "任务结束后不应再留在运行集合里"


def test_run_async_error_callback_and_release(qapp):
    """异常走 on_error，且任务结束后从运行集合移除。"""
    import time

    from PySide6.QtCore import QEventLoop, QTimer
    from pytortoisegit.asyncfw import _live_tasks, run_async

    seen = {}

    def boom():
        time.sleep(0.2)
        raise ValueError("expected failure")

    run_async(boom,
              on_done=lambda r: seen.setdefault("done", r),
              on_error=lambda msg, tb: seen.setdefault("err", (msg, tb)))

    loop = QEventLoop()
    QTimer.singleShot(2000, loop.quit)
    loop.exec()

    assert "done" not in seen, "失败任务不应走 on_done"
    assert "expected failure" in seen.get("err", ("", ""))[0]
    assert not _live_tasks
