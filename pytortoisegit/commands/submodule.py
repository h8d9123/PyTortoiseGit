"""commands/submodule.py —— /command:submodule / subadd / subupdate 入口。

* submodule  —— 打开子模块管理对话框（SubmoduleDlg）
* subadd     —— 打开「添加子模块」对话框并按结果执行 git submodule add
* subupdate  —— 打开「子模块更新」对话框并按结果执行 git submodule update
"""

# PyTortoiseGit - a Python reimplementation mirroring TortoiseGit.
# Copyright (C) 2026  PyTortoiseGit contributors
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# This program is derived from and mirrors the TortoiseGit project.

from __future__ import annotations

import os

from PySide6.QtWidgets import QDialog, QMessageBox

from ..git.submodule import GitSubmodule
from ..res.strings import tr
from ._util import repo_from_cl
from .dispatcher import CommandContext, register


def _update_argv(dlg) -> list:
    """把 SubmoduleUpdateDlg 的选项翻译成 git submodule update 参数。"""
    args = ["submodule", "update"]
    for flag, on in (("--init", dlg.init), ("--recursive", dlg.recursive),
                     ("--force", dlg.force), ("--no-fetch", dlg.no_fetch),
                     ("--merge", dlg.merge), ("--rebase", dlg.rebase),
                     ("--remote", dlg.remote)):
        if on:
            args.append(flag)
    if not dlg.all_selected:
        args += ["--", *dlg.paths]
    return args


@register("submodule")
def submodule(ctx: CommandContext):
    from ..dialogs.submoduledlg import SubmoduleDlg

    repo = repo_from_cl(ctx.cl)
    dlg = SubmoduleDlg(repo, parent=None)
    dlg.exec()
    return "ok"


@register("subadd")
def subadd(ctx: CommandContext):
    from ..dialogs.submoduleadddlg import SubmoduleAddDlg

    repo = repo_from_cl(ctx.cl)
    dlg = SubmoduleAddDlg(repo, parent=None)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return "cancel"
    sub = GitSubmodule(repo)
    if not sub.add(dlg.path, dlg.repository,
                   force=dlg.force, branch=dlg.branch or None):
        QMessageBox.warning(None, tr("error"), tr("submodule_added"))
        return "failed"
    if dlg.putty_key:
        from ..git.git import GitRunner
        GitRunner(cwd=os.path.join(repo.root, dlg.path)).run(
            "config", "remote.origin.puttykeyfile", dlg.putty_key)
    return "ok"


@register("subupdate")
def subupdate(ctx: CommandContext):
    from ..dialogs.submoduleupdatedlg import SubmoduleUpdateDlg

    repo = repo_from_cl(ctx.cl)
    dlg = SubmoduleUpdateDlg(repo, parent=None)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return "cancel"
    result = repo.runner.run(*_update_argv(dlg))
    return "ok" if result.returncode == 0 else "failed"
