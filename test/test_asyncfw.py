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

    注意：宿主已销毁时回调会被防护丢弃（见 _guard_callback），所以这里只断言
    "任务跑完并从运行集合释放、进程没崩"，不断言回调被调用；
    "宿主存活时回调照常执行"由 test_run_async_callback_still_runs_while_parent_alive
    覆盖。
    """
    import time

    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QWidget
    from pytortoisegit.asyncfw import _live_tasks, run_async

    finished = {}

    def slow():
        time.sleep(0.6)
        return 42

    parent_widget = QWidget()
    task = run_async(slow, parent=parent_widget)
    task.finished.connect(lambda: finished.setdefault("done", True))
    parent_widget.deleteLater()

    loop = QEventLoop()
    QTimer.singleShot(2500, loop.quit)
    loop.exec()

    assert finished.get("done") is True, "任务本身应正常跑完"
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


def test_run_async_callback_still_runs_while_parent_alive(qapp):
    """宿主还活着时回调必须照常执行（防护不能误伤正常路径）。"""
    import time

    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QWidget
    from pytortoisegit.asyncfw import run_async

    seen = {}

    def slow():
        time.sleep(0.2)
        return "ok"

    parent = QWidget()
    run_async(slow, on_done=lambda r: seen.setdefault("r", r), parent=parent)
    loop = QEventLoop()
    QTimer.singleShot(1500, loop.quit)
    loop.exec()
    assert seen.get("r") == "ok"


def test_run_async_lambda_callback_skipped_after_parent_destroyed(qapp):
    """宿主销毁后，lambda 回调不得再去碰已析构的 C++ 控件。

    Qt 只能对绑定方法/QObject 槽做销毁时自动断连，lambda 做不到；旧行为是
    回调照常执行并抛 "Internal C++ object already deleted"（在某些路径下会
    直接踩到已释放内存）。防护后应静默丢弃该次回调。
    """
    import time

    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QLabel, QWidget
    from pytortoisegit.asyncfw import run_async

    class Dlg(QWidget):
        def __init__(self):
            super().__init__()
            self.label = QLabel("alive", self)
            self.touched = False
            # 故意用 lambda 捕获 self —— 这正是问题写法
            run_async(self._bg, on_error=lambda m, tb: self._touch(m),
                      parent=self)

        def _bg(self):
            time.sleep(0.4)
            raise RuntimeError("boom")

        def _touch(self, message):
            self.touched = True
            self.label.setText(message)   # 宿主已销毁时这里会炸

    dlg = Dlg()
    dlg.show()
    dlg.close()
    dlg.deleteLater()
    qapp.processEvents()                 # 让 deleteLater 生效

    loop = QEventLoop()
    QTimer.singleShot(1500, loop.quit)
    loop.exec()                          # 任务在此期间失败并尝试回调

    assert dlg.touched is False, "宿主已销毁，回调不应被执行"
