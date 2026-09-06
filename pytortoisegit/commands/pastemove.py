"""commands/pastemove.py —— /command:pastemove（移动文件）。"""

import os, shutil
from PySide6.QtWidgets import QMessageBox
from ..res.strings import tr
from ._util import repo_from_cl
from .dispatcher import CommandContext, register


@register("pastemove")
def pastemove(ctx: CommandContext):
    repo = repo_from_cl(ctx.cl)
    paths = ctx.cl.all_values("path") if ctx.cl else []
    if not paths:
        return "cancel"
    try:
        for p in paths:
            if not os.path.exists(p):
                continue
            from ..dialogs.progress import ProgressDialog
            dlg = ProgressDialog(title=tr("progress", "Progress"),
                                 parent=None, cancellable=False)
            dlg.set_label(os.path.basename(p))
            def _bg():
                shutil.move(p, os.path.join(repo.root, os.path.basename(p)))
                return True
            dlg.run(_bg)
            dlg.exec()
    except Exception as exc:  # noqa: BLE001
        QMessageBox.warning(None, tr("error"), str(exc))
        return "failed"
    return "ok"


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
