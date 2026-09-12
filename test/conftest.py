"""E2E 测试共享基建：Qt 应用、临时仓库、用户操作助手。

设计原则：尽量用 QTest 注入真实输入事件（keyClicks / mouseClick），
真实临时 git 仓库，最后用 git 命令黑盒断言结果。
"""

import os
import time
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


# ---------------------------------------------------------------------------
# 用户操作助手
# ---------------------------------------------------------------------------
class Ui:
    """封装 QTest 的“用户操作”原语。"""

    def wait_until(self, predicate, timeout_ms=10000, interval_ms=20):
        """处理 Qt 事件直到 predicate() 为真或超时。"""
        from PySide6.QtTest import QTest
        deadline = time.monotonic() + timeout_ms / 1000.0
        while time.monotonic() < deadline:
            if predicate():
                return True
            QTest.qWait(interval_ms)
        return bool(predicate())

    def wait(self, ms=50):
        from PySide6.QtTest import QTest
        QTest.qWait(ms)

    def type_text(self, widget, text):
        """模拟用户逐字符输入（\\n 触发回车）。"""
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        widget.setFocus()
        for ch in text:
            if ch == "\n":
                QTest.keyClick(widget, Qt.Key.Key_Return)
            else:
                QTest.keyClicks(widget, ch)

    def set_text(self, widget, text):
        """清空后输入文本（QLineEdit/QPlainTextEdit 通用）。"""
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        widget.setFocus()
        QTest.keyClick(widget, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
        QTest.keyClick(widget, Qt.Key.Key_Delete)
        self.type_text(widget, text)

    def click(self, widget):
        """模拟鼠标左键点击控件。"""
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        QTest.mouseClick(widget, Qt.MouseButton.LeftButton)

    def key(self, widget, key):
        from PySide6.QtTest import QTest
        QTest.keyClick(widget, key)

    def set_combo(self, combo, text):
        """在下拉框中选择/输入文本（尽量模拟用户选择）。"""
        idx = combo.findText(text)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        else:
            combo.setCurrentText(text)


@pytest.fixture
def ui():
    return Ui()


# ---------------------------------------------------------------------------
# 仓库
# ---------------------------------------------------------------------------
def _configure(runner):
    runner.run("config", "user.email", "e2e@example.com")
    runner.run("config", "user.name", "E2E Tester")


@pytest.fixture
def git_repo(tmp_path):
    """全新临时仓库（含一个初始提交）。"""
    from pytortoisegit.git.git import GitRunner
    from pytortoisegit.git.repo import Repository
    runner = GitRunner(cwd=str(tmp_path))
    runner.init(str(tmp_path), initial_branch="main")
    _configure(runner)
    (tmp_path / "a.txt").write_text("line1\nline2\nline3\n", encoding="utf-8")
    assert runner.run("add", "-A").returncode == 0
    assert runner.run("commit", "-m", "initial").returncode == 0
    return Repository.open(str(tmp_path))


@pytest.fixture
def remote_repo(tmp_path):
    """本地 bare 作为 origin，local 已推送 main。"""
    from pytortoisegit.git.git import GitRunner
    from pytortoisegit.git.repo import Repository
    bare = tmp_path / "remote.git"
    GitRunner(cwd=str(tmp_path)).run("init", "--bare", "-b", "main", str(bare))
    local = tmp_path / "local"
    GitRunner(cwd=str(tmp_path)).run("clone", str(bare), str(local))
    lr = GitRunner(cwd=str(local))
    _configure(lr)
    (local / "a.txt").write_text("line1\nline2\nline3\n", encoding="utf-8")
    assert lr.run("add", "-A").returncode == 0
    assert lr.run("commit", "-m", "initial").returncode == 0
    assert lr.run("push", "-u", "origin", "main").returncode == 0
    return SimpleNamespace(local=Repository.open(str(local)), bare=bare, runner=lr)


@pytest.fixture
def auto_progress(monkeypatch):
    """拦截 ProgressDialog.exec：等待后台完成，再模拟用户点“关闭”按钮。"""
    from pytortoisegit.dialogs import progress as progress_mod
    from PySide6.QtTest import QTest

    def fake_exec(self):
        deadline = time.monotonic() + 15.0
        while not self._done and time.monotonic() < deadline:
            QTest.qWait(20)
        # 完成后“中止”按钮已变成“关闭”，点击它即 accept
        if self._done:
            self._btn_cancel.click()
        return self.result()

    monkeypatch.setattr(progress_mod.ProgressDialog, "exec", fake_exec)
