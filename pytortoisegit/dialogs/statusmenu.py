"""statusmenu.py —— 文件状态列表的右键菜单（对齐 CGitStatusListCtrl::OnContextMenuList）。

被「差异 / Show Changed」与提交对话框的文件列表复用：
- git 管理文件：Compare with base / Show changes as unified diff / Commit / Revert /
  Skip worktree / Assume Unchanged / Show log / Blame / Export / View revision /
  Open / Open with / Explore to / Copy to clipboard ...
- 未版本控制文件：Add / Commit / Delete / Ignore / Open ... / Copy to clipboard ...
"""

from __future__ import annotations

import os
import subprocess

from PySide6.QtWidgets import QMenu, QMessageBox

from ..res.strings import format_string, tr


def _full_path(repo, path: str) -> str:
    return os.path.join(repo.root, str(path).replace("/", os.sep))


def _is_unversioned(repo, path: str) -> bool:
    r = repo.runner.run("ls-files", "--error-unmatch", "--", str(path))
    return r.returncode != 0


def _clipboard():
    from ..utils.clipboard import ClipboardHelper
    return ClipboardHelper()


def build_status_menu(parent, repo, path: str, *, on_refresh=None) -> QMenu:
    """构建文件右键菜单（动作已接线；调用方负责 menu.exec 定位）。"""
    path = str(path)
    full = _full_path(repo, path)
    unversioned = _is_unversioned(repo, path)
    menu = QMenu(parent)

    def refresh():
        if on_refresh is not None:
            on_refresh()

    # ---- 顶部：比较（git 管理文件）----
    act_cmp = None
    if not unversioned:
        act_cmp = menu.addAction(tr("statusmenu_compare", "Compare with base"),
                                 lambda: _compare(parent, repo, path))
        menu.setDefaultAction(act_cmp)
        menu.addAction(tr("statusmenu_unified", "Show changes as unified diff"),
                       lambda: _show_unified(parent, repo, path))
        menu.addSeparator()

    if unversioned:
        menu.addAction(tr("statusmenu_add", "Add"),
                       lambda: (_add(repo, path), refresh()))
        menu.addAction(tr("statusmenu_commit", "Commit..."),
                       lambda: _commit(parent, repo, path, refresh))
        menu.addSeparator()
        menu.addAction(tr("statusmenu_delete", "Delete"),
                       lambda: (_delete(parent, repo, path), refresh()))
        menu.addAction(tr("statusmenu_ignore", "Ignore"),
                       lambda: _ignore(parent, repo, path, refresh))
    else:
        menu.addAction(tr("statusmenu_commit", "Commit..."),
                       lambda: _commit(parent, repo, path, refresh))
        menu.addAction(tr("statusmenu_revert", "Revert..."),
                       lambda: (_revert(parent, repo, path), refresh()))
        menu.addAction(tr("statusmenu_skipworktree", "Skip worktree"),
                       lambda: (_update_index(repo, path, "--skip-worktree"), refresh()))
        menu.addAction(tr("statusmenu_assumevalid", "Assume Unchanged"),
                       lambda: (_update_index(repo, path, "--assume-unchanged"), refresh()))

    menu.addSeparator()
    # ---- 日志 / 追溯（单文件）----
    if not unversioned:
        menu.addAction(tr("statusmenu_log", "Show log"),
                       lambda: _show_log(parent, repo, path))
        menu.addAction(tr("statusmenu_blame", "Blame"),
                       lambda: _blame(parent, repo, path))
    menu.addAction(tr("statusmenu_export", "Export selection to...") if not unversioned
                   else tr("statusmenu_saveas", "Save as..."),
                   lambda: _export(parent, repo, path))
    if not unversioned:
        menu.addAction(tr("statusmenu_viewrev", "View revision in alternative editor"),
                       lambda: _view_revision(parent, repo, path))

    menu.addAction(tr("statusmenu_open", "Open"), lambda: _open(full))
    menu.addAction(tr("statusmenu_openwith", "Open with..."),
                   lambda: _open_with(full))
    menu.addAction(tr("statusmenu_explore", "Explore to"),
                   lambda: _explore(full))

    menu.addSeparator()
    clip = menu.addMenu(tr("statusmenu_clipboard", "Copy to clipboard"))
    _add_clip_actions(clip, repo, path)

    menu.addSeparator()
    move = menu.addMenu(tr("statusmenu_movetocs", "Move to changelist"))
    move.setEnabled(False)
    keep = menu.addAction(tr("statusmenu_keepcs", "Keep changelists"))
    keep.setEnabled(False)

    menu.addSeparator()
    shell = menu.addMenu(tr("statusmenu_shell", "Shell"))
    shell.setEnabled(False)

    return menu


# ---------------------------------------------------------------------------
# 动作实现
# ---------------------------------------------------------------------------

def _compare(parent, repo, path):
    """Compare with base：按设置选择外部工具或 TortoiseGitMerge（对齐 StartDiff）。"""
    from ..utils.externaltools import start_diff
    start_diff(parent, repo, path, "HEAD", None)


def _show_unified(parent, repo, path):
    try:
        text = repo.runner.run_checked("diff", "HEAD", "--", path)
    except Exception:  # noqa: BLE001
        return
    from .patchviewdlg import PatchViewDlg
    PatchViewDlg(text, title=path, parent=parent).exec()


def _commit(parent, repo, path, refresh):
    from .commitdlg import CommitDlg
    dlg = CommitDlg(repo, paths=[path], parent=parent)
    dlg.exec()
    refresh()


def _revert(parent, repo, path):
    from PySide6.QtWidgets import QMessageBox
    resp = QMessageBox.question(
        parent, tr("confirm", "Confirm"),
        format_string(tr("statusmenu_revert_q", "Revert changes to {path}?"),
                      path=path),
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    if resp == QMessageBox.StandardButton.Yes:
        repo.runner.run("checkout", "HEAD", "--", path)


def _update_index(repo, path, flag):
    repo.runner.run("update-index", flag, "--", path)


def _add(repo, path):
    repo.runner.run("add", "--", path)


def _delete(parent, repo, path):
    from PySide6.QtWidgets import QMessageBox
    full = _full_path(repo, path)
    resp = QMessageBox.question(
        parent, tr("confirm", "Confirm"),
        format_string(tr("statusmenu_delete_q", "Delete {path}?"), path=path),
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    if resp == QMessageBox.StandardButton.Yes and os.path.exists(full):
        if os.path.isdir(full):
            import shutil
            shutil.rmtree(full, ignore_errors=True)
        else:
            os.remove(full)


def _ignore(parent, repo, path, refresh):
    from .ignoredlg import IgnoreDlg
    dlg = IgnoreDlg(repo, paths=[path], parent=parent)
    dlg.exec()
    refresh()


def _show_log(parent, repo, path):
    from .logdlg import LogDlg
    LogDlg(repo, pathspec=path, parent=parent).exec()


def _blame(parent, repo, path):
    from .blamedlg import BlameDlg
    BlameDlg(repo, path, parent=parent).exec()


def _export(parent, repo, path):
    from PySide6.QtWidgets import QFileDialog
    dest, _ = QFileDialog.getSaveFileName(
        parent, tr("statusmenu_export", "Export selection to..."),
        os.path.basename(path))
    if not dest:
        return
    src = _full_path(repo, path)
    if os.path.isfile(src):
        import shutil
        shutil.copyfile(src, dest)


def _view_revision(parent, repo, path):
    from .settingsdlg import general_settings
    s = general_settings()
    if not bool(s.value("AlternativeEditorUseCustom", 0, type=int)):
        QMessageBox.information(
            parent, tr("statusmenu_viewrev", "View revision in alternative editor"),
            tr("statusmenu_no_editor",
               "No alternative editor configured (see Settings > Alternative editor)."))
        return
    editor = str(s.value("AlternativeEditor", "") or "")
    full = _full_path(repo, path)
    if not editor or not os.path.isfile(full):
        return
    try:
        subprocess.Popen([editor, full])
    except OSError:
        pass


def _open(full):
    if os.path.isfile(full):
        os.startfile(full)  # noqa: S606


def _open_with(full):
    if os.path.isfile(full):
        try:
            subprocess.Popen(["rundll32.exe", "shell32.dll,OpenAs_RunDLL", full])
        except OSError:
            pass


def _explore(full):
    try:
        if os.path.isdir(full):
            os.startfile(full)  # noqa: S606
        else:
            subprocess.Popen(["explorer", "/select,", full])
    except OSError:
        pass


def _add_clip_actions(menu, repo, path):
    full = _full_path(repo, path)
    menu.addAction(tr("statusmenu_copy_full", "Full path"),
                   lambda: _clipboard().copy_text(full))
    menu.addAction(tr("statusmenu_copy_rel", "Relative path"),
                   lambda: _clipboard().copy_text(path))
    menu.addAction(tr("statusmenu_copy_name", "File name"),
                   lambda: _clipboard().copy_text(os.path.basename(path)))
    menu.addAction(tr("statusmenu_copy_ext", "Extended path"),
                   lambda: _clipboard().copy_text(full))
