# PyTortoiseGit - a Python reimplementation mirroring TortoiseGit.
# Copyright (C) 2026  PyTortoiseGit contributors
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.

"""loglists.py —— 对齐 GitLogList / GitStatusListCtrl 的列定义与文件行解析。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List

from ..res.strings import tr

# 日志列顺序对齐 CGitLogListBase::InsertGitColumn（普通 Log 默认可见前 5 列）
LOG_COL_GRAPH = 0
LOG_COL_ACTIONS = 1
LOG_COL_MESSAGE = 2
LOG_COL_AUTHOR = 3
LOG_COL_DATE = 4
LOG_COL_HASH = 5
LOG_COL_EMAIL = 6
LOG_COL_COMMIT_NAME = 7
LOG_COL_COMMIT_EMAIL = 8
LOG_COL_COMMIT_DATE = 9

# 文件列对齐 GitStatusListCtrl（eCol_Name..eCol_FileSize）
FILE_COL_PATH = 0
FILE_COL_FILENAME = 1
FILE_COL_EXT = 2
FILE_COL_STATUS = 3
FILE_COL_ADD = 4
FILE_COL_DEL = 5
FILE_COL_MODIFIED = 6
FILE_COL_SIZE = 7


def log_column_labels() -> List[str]:
    return [
        tr("log_graph", "Graph"),
        tr("log_actions", "Action"),
        tr("log_message", "Message"),
        tr("log_author", "Author"),
        tr("log_date", "Date"),
        tr("log_hash", "SHA-1"),
        tr("log_email", "E-mail"),
        tr("log_commit_name", "Committer"),
        tr("log_commit_email", "Committer E-mail"),
        tr("log_commit_date", "Commit date"),
    ]


def log_default_hidden() -> tuple:
    return (LOG_COL_HASH, LOG_COL_EMAIL, LOG_COL_COMMIT_NAME,
            LOG_COL_COMMIT_EMAIL, LOG_COL_COMMIT_DATE)


def file_column_labels() -> List[str]:
    return [
        tr("log_file_path", "File"),
        tr("log_file_filename", "File name"),
        tr("log_file_ext", "Extension"),
        tr("log_file_status", "Status"),
        tr("log_file_add", "Added"),
        tr("log_file_del", "Deleted"),
        tr("log_file_modified", "Modified"),
        tr("log_file_size", "Size"),
    ]


def file_default_hidden() -> tuple:
    return (FILE_COL_FILENAME, FILE_COL_MODIFIED, FILE_COL_SIZE)


# Colors.cpp 默认：Modified / Added / Deleted / Renamed / Conflict
_STATUS_COLOR = {
    "M": (0, 50, 160),
    "A": (100, 0, 100),
    "D": (100, 0, 0),
    "R": (0, 0, 255),
    "C": (100, 0, 100),
    "U": (255, 0, 0),
    "T": (0, 50, 160),
}


_STATUS_TEXT = {
    "M": lambda: tr("log_st_modified", "Modified"),
    "A": lambda: tr("log_st_added", "Added"),
    "D": lambda: tr("log_st_deleted", "Deleted"),
    "R": lambda: tr("log_st_renamed", "Renamed"),
    "C": lambda: tr("log_st_copied", "Copied"),
    "T": lambda: tr("log_st_type", "Type changed"),
    "U": lambda: tr("log_st_unmerged", "Unmerged"),
}


def status_text(code: str) -> str:
    key = (code or "?").lstrip()[:1].upper()
    fn = _STATUS_TEXT.get(key)
    return fn() if fn else code


def status_color(code: str):
    key = (code or "?").lstrip()[:1].upper()
    return _STATUS_COLOR.get(key)


def filediff_action_color(code: str):
    """CFileDiffDlg::OnNMCustomdrawFilelist：A/D/M 用对应色，其余 PropertyChanged。"""
    key = (code or "?").lstrip()[:1].upper()
    if key == "A":
        return (100, 0, 100)
    if key == "D":
        return (100, 0, 0)
    return (0, 50, 160)


@dataclass
class ChangedFile:
    path: str
    status: str
    added: str = ""
    deleted: str = ""
    old_path: str = ""
    parent: int = 0  # 合并时的父提交序号（0 起）

    @property
    def ext(self) -> str:
        base = os.path.basename(self.path)
        _, dot, rest = base.rpartition(".")
        return ("." + rest) if dot and rest else ""

    @property
    def filename(self) -> str:
        return os.path.basename(self.path.replace("\\", "/"))

    def display_name(self) -> str:
        """对齐 GetCellText(eCol_Name)：重命名显示「新 (来自 旧)」。"""
        if not self.old_path:
            return self.path
        # 对齐 GetCellText(eCol_Name)：path + " " + IDS_STATUSLIST_FROM
        return self.path + " " + tr("log_file_from", "(from {})").format(self.old_path)


def parse_show_files(text: str) -> List[ChangedFile]:
    """解析 `git show --format= --name-status --numstat`。"""
    by_path: dict[str, ChangedFile] = {}
    order: List[str] = []
    for raw in (text or "").splitlines():
        line = raw.rstrip("\r")
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        if parts[0][:1].isdigit() or parts[0] in ("-", "−"):
            added, deleted, path = parts[0], parts[1], parts[-1]
            row = by_path.get(path)
            if row is None:
                row = ChangedFile(path, "M", added, deleted)
                by_path[path] = row
                order.append(path)
            else:
                row.added, row.deleted = added, deleted
            continue
        code = parts[0]
        if len(parts) >= 3 and code[:1] in "RC":
            old, path = parts[1], parts[2]
            row = ChangedFile(path, code, old_path=old)
        else:
            path = parts[-1]
            row = ChangedFile(path, code)
        if path not in by_path:
            order.append(path)
        by_path[path] = row
    return [by_path[p] for p in order]
