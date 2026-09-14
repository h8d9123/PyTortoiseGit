"""sshkeys.py —— SSH 客户端 / PuTTY 相关判定与工具定位。

对齐 TortoiseGit 的 CAppUtils::IsSSHPutty / SSH 客户端设置。
"""

from __future__ import annotations

import os
import shutil


def ssh_client_path() -> str:
    """当前配置的 SSH 客户端路径（设置页 sshClient > GIT_SSH* > 空）。"""
    ssh = ""
    try:
        from ..dialogs.settingsdlg import general_settings
        ssh = str(general_settings().value("sshClient", "") or "")
    except Exception:  # noqa: BLE001
        pass
    return (ssh or os.environ.get("GIT_SSH", "")
            or os.environ.get("GIT_SSH_COMMAND", ""))


def is_ssh_putty() -> bool:
    """SSH 客户端是否为 PuTTY/Plink（对齐 CAppUtils::IsSSHPutty）。"""
    return "plink" in os.path.basename(ssh_client_path()).lower()


def find_puttygen() -> str:
    """定位 puttygen.exe（PATH 或常见安装目录），未找到返回空串。"""
    for name in ("puttygen", "puttygen.exe"):
        p = shutil.which(name)
        if p:
            return p
    for base in (os.environ.get("ProgramFiles", ""),
                 os.environ.get("ProgramFiles(x86)", "")):
        if not base:
            continue
        for sub in (r"PuTTY", r"TortoiseGit\bin"):
            cand = os.path.join(base, sub, "puttygen.exe")
            if os.path.isfile(cand):
                return cand
    return ""


def key_ssh_command(key_path: str) -> str:
    """用密钥构造 core.sshCommand 值（PuTTY 用 plink -i，否则 ssh -i）。"""
    client = ssh_client_path()
    if is_ssh_putty() and client:
        return f'"{client}" -i "{key_path}"'
    return f'ssh -i "{key_path}"'
