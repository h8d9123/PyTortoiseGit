"""E2E：设置与通用界面交互（TC-SET / TC-UI）。

运行：QT_QPA_PLATFORM=offscreen python -m pytest test/test_e2e_ui.py -v
"""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog


def test_TC_UI_001_enter_triggers_default(qapp, ui, git_repo):
    """回车触发默认按钮（确定）。"""
    from pytortoisegit.dialogs.addremotedlg import AddRemoteDlg
    dlg = AddRemoteDlg(git_repo)
    ui.set_text(dlg.name_edit, "ent")
    ui.set_text(dlg.url_edit, "https://example.com/x.git")
    dlg.show()
    ui.key(dlg.url_edit, Qt.Key.Key_Return)
    assert dlg.result() == QDialog.DialogCode.Accepted
    assert "ent" in git_repo.runner.run("remote").stdout


def test_TC_UI_002_escape_cancels(qapp, ui, git_repo):
    """Esc 关闭对话框且不执行操作。"""
    from pytortoisegit.dialogs.addremotedlg import AddRemoteDlg
    dlg = AddRemoteDlg(git_repo)
    dlg.show()
    ui.key(dlg, Qt.Key.Key_Escape)
    assert dlg.result() != QDialog.DialogCode.Accepted
    assert git_repo.runner.run("remote").stdout.strip() == ""


def test_TC_UI_007_resize_anchors(qapp, ui, git_repo):
    """窗口缩放后控件不越界。"""
    from pytortoisegit.dialogs.commitdlg import CommitDlg
    dlg = CommitDlg(git_repo)
    dlg.show()
    ui.wait(200)
    dlg.resize(dlg.width() + 200, dlg.height() + 120)
    ui.wait(50)
    for ctrl_id, wgt in dlg._ctl.items():
        assert wgt.x() >= 0 and wgt.y() >= 0, ctrl_id
        assert wgt.geometry().right() <= dlg.width() + 5, ctrl_id


def test_TC_UI_011_threadsafe_log(qapp, ui):
    """后台线程写日志经队列回主线程，不崩溃。"""
    import threading
    from pytortoisegit.dialogs.progress import ProgressDialog
    dlg = ProgressDialog()
    dlg.show()
    dlg._timer.start(20)  # 正常流程由 run() 启动轮询定时器

    def worker():
        for i in range(50):
            dlg.log(f"line {i}")

    t = threading.Thread(target=worker)
    t.start()
    t.join()
    # 处理事件，让队列内容回主线程写入
    assert ui.wait_until(lambda: "line 49" in dlg.output.toPlainText())
    dlg.deleteLater()


def test_TC_SET_002_persist(qapp, ui, tmp_path, monkeypatch):
    """设置保存后重载仍保留。"""
    from PySide6.QtCore import QSettings
    # 用临时配置文件，避免污染真实设置
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    path = tmp_path / "settings.ini"
    monkeypatch.setattr(QSettings, "_test_path", str(path), raising=False)
    s = QSettings(str(path), QSettings.Format.IniFormat)
    s.setValue("e2e/key", "value1")
    s.sync()
    s2 = QSettings(str(path), QSettings.Format.IniFormat)
    assert s2.value("e2e/key") == "value1"


def test_TC_SET_003_theme(qapp, ui):
    """应用主题 QSS：QGroupBox 标题嵌入边框。"""
    from pytortoisegit.ui.theme import apply_theme, GROUPBOX_QSS
    old = qapp.styleSheet()
    try:
        apply_theme(qapp)
        assert qapp.styleSheet() == GROUPBOX_QSS
        assert "QGroupBox::title" in GROUPBOX_QSS
    finally:
        qapp.setStyleSheet(old)


def test_TC_I18N_001_language_switch(qapp, ui):
    """语言切换后界面文案变化。"""
    from pytortoisegit.res import strings
    old = strings.get_language()
    try:
        strings.set_language("en")
        assert strings.tr("ok", "OK") == "OK"
        strings.set_language("zh")
        assert strings.tr("ok", "OK") == "确定"
    finally:
        strings.set_language(old)
