"""logging_utils 测试：日志文件与异常钩子。"""

import os
import sys

from pytortoisegit.utils.logging_utils import get_logger, install_excepthooks


def _logpath() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "PyTortoiseGit", "pytortoisegit.log")


def test_logger_writes_file():
    get_logger("test_logger").info("hello world")
    content = open(_logpath(), encoding="utf-8").read()
    assert "hello world" in content


def test_excepthook_logs_and_swallows():
    install_excepthooks(show_dialog=False)
    try:
        raise ValueError("boom-test")
    except ValueError as exc:
        sys.excepthook(type(exc), exc, exc.__traceback__)
    content = open(_logpath(), encoding="utf-8").read()
    assert "boom-test" in content
    assert "ValueError" in content