"""demo.py —— 一键演示 PyTortoiseGit 阶段 1 的 About 对话框。

用法：python demo.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    from PySide6.QtWidgets import QApplication
    from pytortoisegit.dialogs.aboutdlg import AboutDlg

    qapp = QApplication.instance() or QApplication(sys.argv)
    dlg = AboutDlg()
    dlg.show()
    return qapp.exec()


if __name__ == "__main__":
    raise SystemExit(main())