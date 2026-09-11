"""ui/theme.py —— 跨平台外观统一。

QGroupBox 的标题位置由 Qt 平台样式决定：
  * Windows 原生样式（windowsvista/windows11）把标题嵌进上边框；
  * Linux/macOS 常用的 Fusion / GTK 样式把标题画在边框上方。
这会导致同一对话框在不同平台观感不一致（分组框与首行控件贴得过近）。

这里用样式表统一成「标题嵌入边框」，各平台渲染一致。
"""

from __future__ import annotations

GROUPBOX_QSS = """
QGroupBox {
    border: 1px solid #9a9a9a;
    border-radius: 3px;
    margin-top: 8px;
    padding-top: 2px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 9px;
    padding: 0 3px;
}
"""


def apply_theme(app) -> None:
    """给 QApplication 安装统一主题（当前仅统一 QGroupBox 外观）。"""
    app.setStyleSheet(GROUPBOX_QSS)
