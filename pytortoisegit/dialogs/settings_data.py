"""settings_data.py —— 设置页的数据模型（Hooks / BugTraq 关联）。

存储使用应用级 QSettings（键名对齐 TortoiseGit 注册表），
由 settingsdlg.general_settings 提供（测试会 monkeypatch 到临时 INI）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

# ---------------------------------------------------------------------------
# Hooks
# ---------------------------------------------------------------------------

# (类型键, 显示 tr 键, 默认英文) —— 与 CHooks::GetHookTypeString 一致
HOOK_TYPES = [
    ("start_commit_hook", "hook_type_startcommit", "Start Commit Hook"),
    ("pre_commit_hook", "hook_type_precommit", "Pre-Commit Hook"),
    ("post_commit_hook", "hook_type_postcommit", "Post-Commit Hook"),
    ("pre_push_hook", "hook_type_prepush", "Pre-Push Hook"),
    ("post_push_hook", "hook_type_postpush", "Post-Push Hook"),
    ("pre_rebase_hook", "hook_type_prerebase", "Pre-Rebase Hook"),
]

_HOOK_SETTINGS_KEY = "Hooks"


@dataclass
class Hook:
    htype: str = "pre_commit_hook"
    path: str = ""
    commandline: str = ""
    wait: bool = True
    show: bool = True
    enabled: bool = True
    local: bool = False

    def to_dict(self) -> dict:
        return {
            "htype": self.htype, "path": self.path,
            "commandline": self.commandline, "wait": self.wait,
            "show": self.show, "enabled": self.enabled, "local": self.local,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Hook":
        return cls(
            htype=str(d.get("htype", "pre_commit_hook")),
            path=str(d.get("path", "")),
            commandline=str(d.get("commandline", "")),
            wait=bool(d.get("wait", True)),
            show=bool(d.get("show", True)),
            enabled=bool(d.get("enabled", True)),
            local=bool(d.get("local", False)),
        )

    def key(self) -> tuple:
        return (self.htype, self.local, self.path)


def load_hooks() -> List[Hook]:
    from .settingsdlg import general_settings
    raw = general_settings().value(_HOOK_SETTINGS_KEY, [], type=list) or []
    out: List[Hook] = []
    for item in raw:
        if isinstance(item, dict):
            out.append(Hook.from_dict(item))
    return out


def save_hooks(hooks: List[Hook]) -> None:
    from .settingsdlg import general_settings
    s = general_settings()
    s.setValue(_HOOK_SETTINGS_KEY, [h.to_dict() for h in hooks])
    s.sync()


# ---------------------------------------------------------------------------
# BugTraq associations
# ---------------------------------------------------------------------------

_BUGTRAQ_SETTINGS_KEY = "BugTraqAssociations"


@dataclass
class BugTraqAssociation:
    path: str = ""
    provider: str = ""
    parameters: str = ""
    enabled: bool = True

    def to_dict(self) -> dict:
        return {
            "path": self.path, "provider": self.provider,
            "parameters": self.parameters, "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BugTraqAssociation":
        return cls(
            path=str(d.get("path", "")),
            provider=str(d.get("provider", "")),
            parameters=str(d.get("parameters", "")),
            enabled=bool(d.get("enabled", True)),
        )


def load_bugtraq_associations() -> List[BugTraqAssociation]:
    from .settingsdlg import general_settings
    raw = general_settings().value(_BUGTRAQ_SETTINGS_KEY, [], type=list) or []
    out: List[BugTraqAssociation] = []
    for item in raw:
        if isinstance(item, dict):
            out.append(BugTraqAssociation.from_dict(item))
    return out


def save_bugtraq_associations(assocs: List[BugTraqAssociation]) -> None:
    from .settingsdlg import general_settings
    s = general_settings()
    s.setValue(_BUGTRAQ_SETTINGS_KEY, [a.to_dict() for a in assocs])
    s.sync()
