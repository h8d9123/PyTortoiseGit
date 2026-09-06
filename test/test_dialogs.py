"""对话框冒烟测试（需要 GUI 平台；无桌面环境可设 QT_QPA_PLATFORM=offscreen）。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from pytortoisegit.cmdline import parse
from pytortoisegit.commands.dispatcher import CommandContext, dispatch


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _run_with_autoclose(qapp, verb, args):
    """执行命令，通过钩子拿到对话框后单发计时器自动关闭。"""
    from PySide6.QtCore import QTimer

    cl = parse(args)
    result = {"rc": None}

    def _prepare(dlg):
        QTimer.singleShot(0, dlg.accept)

    ctx = CommandContext(qapp=qapp, cl=cl, hooks={"about_prepare": _prepare})
    dispatch(verb, ctx)
    return cl


def test_about_command_opens_and_closes(qapp):
    _run_with_autoclose(qapp, "about", "/command:about")


def test_about_dialog_title(qapp):
    from pytortoisegit.dialogs.aboutdlg import AboutDlg
    dlg = AboutDlg()
    assert "关于" in dlg.windowTitle()
    dlg.deleteLater()


def test_unknown_command():
    from pytortoisegit.commands.dispatcher import UnknownCommandError, dispatch
    from pytortoisegit.cmdline import parse
    from pytortoisegit.cmdline import CommandLine

    ctx = CommandContext(cl=parse("/command:definitely_not_a_real_cmd"))
    with pytest.raises(UnknownCommandError):
        dispatch("definitely_not_a_real_cmd", ctx)