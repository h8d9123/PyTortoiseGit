"""scripts/screenshots.py —— 生成各主要对话框截图到 screenshots/。

用法：
    python scripts/screenshots.py            # 全部
    python scripts/screenshots.py settings   # 只生成指定窗口

默认使用 offscreen 平台，可在无显示环境运行。
"""

from __future__ import annotations

import os
import sys
import tempfile
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

OUT = os.path.join(ROOT, "screenshots")


def _pump(app, seconds: float):
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def _shot(app, widget, name: str, wait: float = 1.0):
    widget.show()
    _pump(app, wait)
    path = os.path.join(OUT, name + ".png")
    widget.grab().save(path)
    print("saved", os.path.relpath(path, ROOT))
    widget.close()
    widget.deleteLater()
    _pump(app, 0.1)


def _use_cjk_font(app):
    """offscreen 默认字体无中文字形，挑一个系统 CJK 字体避免显示成方块。"""
    from PySide6.QtGui import QFont, QFontDatabase
    try:
        families = set(QFontDatabase.families())
    except Exception:
        return
    for cand in ("Microsoft YaHei", "SimSun", "Noto Sans CJK SC",
                 "Source Han Sans SC", "WenQuanYi Micro Hei", "PingFang SC"):
        if cand in families:
            app.setFont(QFont(cand, 9))
            print("font:", cand)
            return


def _make_repo():
    from pytortoisegit.git.git import GitRunner
    from pytortoisegit.git.repo import Repository
    d = tempfile.mkdtemp()
    r = GitRunner(cwd=d)
    r.init(d, initial_branch="main")
    repo = Repository.open(d)
    r.run("config", "user.email", "demo@example.com")
    r.run("config", "user.name", "Demo")
    for i in range(3):
        with open(os.path.join(d, f"file{i}.txt"), "w", encoding="utf-8") as fh:
            fh.write(f"line {i}\n")
        r.run("add", "-A")
        r.run("commit", "-m", f"commit {i}")
    r.run("tag", "v1.0")
    r.run("checkout", "-b", "feature")
    with open(os.path.join(d, "feature.txt"), "w", encoding="utf-8") as fh:
        fh.write("feature\n")
    r.run("add", "-A")
    r.run("commit", "-m", "feature work")
    r.run("checkout", "main")
    with open(os.path.join(d, "file0.txt"), "w", encoding="utf-8") as fh:
        fh.write("line 0 modified\n")
    r.run("add", "-A")
    r.run("commit", "-m", "main work")
    r.run("merge", "--no-ff", "feature", "-m", "merge feature")
    return repo


def main(argv):
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    _use_cjk_font(app)
    os.makedirs(OUT, exist_ok=True)
    want = set(argv) if argv else None

    def should(name):
        return want is None or name in want

    repo = _make_repo()

    if should("settings"):
        from pytortoisegit.dialogs.settingsdlg import SettingsDlg
        dlg = SettingsDlg(repo)
        for key, label in (("main", "settings_general"),
                           ("diff", "settings_diff"),
                           ("proxy", "settings_network"),
                           ("smtp", "settings_email"),
                           ("blame", "settings_blame"),
                           ("udiff", "settings_udiff"),
                           ("advanced", "settings_advanced")):
            item = dlg._items.get(key)
            if item is not None:
                dlg.tree.setCurrentItem(item)
            _shot(app, dlg, label, wait=0.5)

    if should("log"):
        from pytortoisegit.dialogs.logdlg import LogDlg
        _shot(app, LogDlg(repo), "log", wait=2.0)

    if should("reflog"):
        from pytortoisegit.dialogs.reflogdlg import ReflogDlg
        _shot(app, ReflogDlg(repo), "reflog", wait=2.0)

    if should("diff"):
        from pytortoisegit.dialogs.diffdlg import DiffDlg
        _shot(app, DiffDlg(repo, "HEAD~1", "HEAD"), "diff", wait=2.0)

    if should("merge"):
        from pytortoisegit.dialogs.mergedlg import MergeDlg
        _shot(app, MergeDlg(repo), "merge", wait=1.0)

    if should("revisiongraph"):
        from pytortoisegit.dialogs.revisiongraphdlg import RevisionGraphDlg
        _shot(app, RevisionGraphDlg(repo), "revisiongraph", wait=2.0)

    if should("commit"):
        from pytortoisegit.dialogs.commitdlg import CommitDlg
        _shot(app, CommitDlg(repo), "commit", wait=1.5)

    if should("clone"):
        from pytortoisegit.dialogs.clonedlg import CloneDlg
        _shot(app, CloneDlg(), "clone", wait=1.0)

    if should("switch"):
        from pytortoisegit.dialogs.gitswitchdlg import GitSwitchDlg
        _shot(app, GitSwitchDlg(repo), "switch", wait=1.0)

    if should("mainwindow"):
        from pytortoisegit.dialogs.mainmenu import MainMenuDlg
        dlg = MainMenuDlg(repo_path=str(repo.root))
        _shot(app, dlg, "mainwindow", wait=1.5)
        menu = dlg._build_blank_menu(str(repo.root), dlg.content_list)
        menu.popup(dlg.mapToGlobal(dlg.rect().center()))
        _pump(app, 0.4)
        menu.grab().save(os.path.join(OUT, "contextmenu.png"))
        print("saved screenshots/contextmenu.png")
        menu.close()
        dlg.deleteLater()

    print("done ->", os.path.relpath(OUT, ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
