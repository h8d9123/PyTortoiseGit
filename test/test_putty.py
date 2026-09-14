"""PuTTY 相关处理一致性测试（sshkeys 助手 + 各对话框置灰）。"""

import pytest


@pytest.fixture(autouse=True)
def _english_ui():
    from pytortoisegit.res import strings
    strings.set_language("en")
    yield
    strings.set_language("zh")


@pytest.fixture(autouse=True)
def _clean_ssh(monkeypatch):
    monkeypatch.delenv("GIT_SSH", raising=False)
    monkeypatch.delenv("GIT_SSH_COMMAND", raising=False)
    monkeypatch.setattr("pytortoisegit.dialogs.settingsdlg.general_settings",
                        lambda: _EmptySettings())


class _EmptySettings:
    def value(self, *a, **k):
        return ""

    def setValue(self, *a, **k):
        pass

    def sync(self):
        pass


def test_is_ssh_putty(monkeypatch):
    from pytortoisegit.utils import sshkeys
    assert sshkeys.is_ssh_putty() is False
    monkeypatch.setenv("GIT_SSH", r"C:\Tools\plink.exe")
    assert sshkeys.is_ssh_putty() is True
    monkeypatch.setenv("GIT_SSH", r"C:\Tools\ssh.exe")
    assert sshkeys.is_ssh_putty() is False


def test_key_ssh_command(monkeypatch):
    from pytortoisegit.utils import sshkeys
    assert sshkeys.key_ssh_command("C:/k.ppk").startswith("ssh -i")
    monkeypatch.setenv("GIT_SSH", r"C:\Tools\plink.exe")
    assert "plink.exe" in sshkeys.key_ssh_command("C:/k.ppk")


def test_pull_push_sync_putty_grayed(qapp, monkeypatch):
    monkeypatch.setattr("pytortoisegit.utils.sshkeys.is_ssh_putty", lambda: False)
    from pytortoisegit.git.git import GitRunner
    from pytortoisegit.git.repo import Repository
    import tempfile
    d = tempfile.mkdtemp()
    r = GitRunner(cwd=d)
    r.run("init", "-b", "main", d)
    r.run("config", "user.email", "t@e.com")
    r.run("config", "user.name", "T")
    repo = Repository.open(d)

    from pytortoisegit.dialogs.pulldlg import PullFetchDlg
    from pytortoisegit.dialogs.pushdlg import PushDlg
    from pytortoisegit.dialogs.sync import SyncDlg
    assert not PullFetchDlg(repo).chk_putty.isEnabled()
    assert not PushDlg(repo).chk_putty.isEnabled()
    assert not SyncDlg(repo).chk_putty.isEnabled()


def test_firststart_genkey_grayed(qapp, monkeypatch):
    monkeypatch.setattr("pytortoisegit.utils.sshkeys.find_puttygen", lambda: "")
    from pytortoisegit.dialogs.firststartdlg import _AuthPage
    page = _AuthPage()
    assert not page.btn_genkey.isEnabled()
