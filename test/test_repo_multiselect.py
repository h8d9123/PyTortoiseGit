"""仓库管理面板多选（Ctrl/Shift）行为测试。

覆盖：
  * 树启用 ExtendedSelection（Ctrl 点选 / Shift 连选 / 框选）；
  * 选中集合 → 路径集合（子模块折算到父仓库根，去重）；
  * 右键批量移除、批量打开、批量运行命令；
  * 重建树后选中项保留（分支/提交后台补齐不会丢选中）。
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402


def _make_repos(tmp_path, count=2):
    """创建 count 个各自独立的临时仓库，返回路径列表。"""
    from pytortoisegit.git.git import GitRunner
    paths = []
    for i in range(count):
        root = tmp_path / f"repo{i}"
        root.mkdir()
        runner = GitRunner(cwd=str(root))
        runner.init(str(root), initial_branch="main")
        runner.run("config", "user.email", "t@example.com")
        runner.run("config", "user.name", "Tester")
        (root / "a.txt").write_text(f"{i}\n", encoding="utf-8")
        runner.run("add", "-A")
        assert runner.run("commit", "-m", f"init{i}").returncode == 0
        paths.append(str(root))
    return paths


@pytest.fixture
def repos(tmp_path):
    """两个独立仓库（已在磁盘提交），返回路径列表。"""
    return _make_repos(tmp_path, 2)


@pytest.fixture()
def isolated_settings(tmp_path, monkeypatch):
    """把 general_settings 隔离到临时 INI 文件，避免污染真实注册表。"""
    from PySide6.QtCore import QSettings
    s = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(
        "pytortoisegit.dialogs.settingsdlg.general_settings", lambda: s)
    return s


def _dlg_with(repos):
    """打开主窗口并把给定仓库全部加入管理列表。"""
    from pytortoisegit.dialogs.mainmenu import MainMenuDlg
    dlg = MainMenuDlg()
    dlg._repo_list = list(repos)
    dlg._save_repo_list()
    dlg._refresh_repo_tree()
    assert dlg.repo_tree.topLevelItemCount() == len(repos)
    return dlg


def test_repo_tree_supports_ctrl_shift_multiselect(qapp, repos, isolated_settings):
    """树为 ExtendedSelection + SelectRows：等价于 Ctrl 点选 / Shift 连选。"""
    from PySide6.QtWidgets import QAbstractItemView

    dlg = _dlg_with(repos)
    tree = dlg.repo_tree
    assert tree.selectionMode() == \
        QAbstractItemView.SelectionMode.ExtendedSelection
    assert tree.selectionBehavior() == \
        QAbstractItemView.SelectionBehavior.SelectRows

    # 模拟 Ctrl 点选：逐个追加选中
    first = tree.topLevelItem(0)
    second = tree.topLevelItem(1)
    tree.setCurrentItem(first)
    first.setSelected(True)
    assert not dlg._multi_selected()
    second.setSelected(True)
    assert dlg._multi_selected()
    assert {os.path.normcase(p) for p in dlg._selected_repo_paths()} == \
        {os.path.normcase(p) for p in repos}

    # 取消第二个 → 回到单选
    second.setSelected(False)
    assert not dlg._multi_selected()
    assert dlg._selected_repo_paths() == [repos[0]]
    dlg.reject()


def test_repo_multiselect_status_and_content(qapp, repos, isolated_settings):
    """多选：状态栏显示计数，右侧内容区不跟随跳转。"""
    dlg = _dlg_with(repos)
    tree = dlg.repo_tree
    tree.setCurrentItem(tree.topLevelItem(0))
    tree.topLevelItem(0).setSelected(True)
    dlg._on_repo_clicked(tree.topLevelItem(0), 0)
    assert os.path.normcase(dlg._nav_current or "") == \
        os.path.normcase(repos[0])

    before = dlg._nav_current
    tree.topLevelItem(1).setSelected(True)
    dlg._on_repo_clicked(tree.topLevelItem(1), 0)
    assert dlg._nav_current == before, "多选时不应切换右侧内容"
    assert "2" in dlg.status.text(), dlg.status.text()
    dlg.reject()


def test_repo_tree_keeps_selection_after_refresh(qapp, repos, isolated_settings):
    """重建树（含后台补齐分支/提交）后多选保持不丢。"""
    dlg = _dlg_with(repos)
    tree = dlg.repo_tree
    tree.setCurrentItem(tree.topLevelItem(0))
    tree.topLevelItem(0).setSelected(True)
    tree.topLevelItem(1).setSelected(True)

    dlg._refresh_repo_tree()
    assert dlg._multi_selected()
    assert {os.path.normcase(p) for p in dlg._selected_repo_paths()} == \
        {os.path.normcase(p) for p in repos}
    dlg.reject()


def test_repo_multiselect_remove_all(qapp, repos, isolated_settings):
    """右键「从列表移除」在多选时移除全部选中仓库。"""
    dlg = _dlg_with(repos)
    tree = dlg.repo_tree
    tree.setCurrentItem(tree.topLevelItem(0))
    for i in range(tree.topLevelItemCount()):
        tree.topLevelItem(i).setSelected(True)

    dlg._remove_repos_from_list(dlg._selected_repo_items())
    assert dlg._repo_list == []
    assert tree.topLevelItemCount() == 0
    assert dlg._load_repo_list() == []
    dlg.reject()


def test_repo_multiselect_actions_apply_to_all(qapp, repos, isolated_settings):
    """多选菜单：批量打开 + 批量运行命令作用于每个选中仓库。"""
    from PySide6.QtWidgets import QMenu

    dlg = _dlg_with(repos)
    tree = dlg.repo_tree
    tree.setCurrentItem(tree.topLevelItem(0))
    tree.topLevelItem(0).setSelected(True)
    tree.topLevelItem(1).setSelected(True)

    # 打开全部选中仓库：最后一个成为当前仓库
    dlg._open_repos(dlg._selected_repo_roots())
    assert os.path.normcase(dlg.repo.root) == os.path.normcase(repos[-1])

    # 批量命令：一条命令对每个选中仓库各分发一次
    calls = []
    dlg._dispatch = lambda name, extra=None: calls.append(
        (name, os.path.normcase(extra["path"]) if extra else None))
    menu = QMenu(tree)
    dlg._add_multi_repo_actions(menu)
    labels = [a.text() for a in menu.actions() if a.text()]
    assert any("2" in t for t in labels), labels

    batch = [m for m in menu.findChildren(QMenu) if m.actions()]
    assert batch, "应有「对选中仓库运行」子菜单"
    act = batch[0].actions()[0]
    act.trigger()
    assert calls, "批量菜单项应分发命令"
    name, _ = calls[0]
    assert len(calls) == 2
    assert {c[1] for c in calls} == {os.path.normcase(p) for p in repos}
    dlg.reject()


def test_repo_batch_menu_merges_states(qapp, repos, isolated_settings):
    """批量菜单取各仓库 itemStates 的并集，任一可用即显示。"""
    from PySide6.QtWidgets import QMenu
    from pytortoisegit import menuitems as mi

    dlg = _dlg_with(repos)
    menu = QMenu(dlg.repo_tree)
    added = dlg._populate_batch_menu(menu, repos)
    assert added > 0
    cmds = [a.text() for a in menu.actions() if a.text()]
    # 仓库已存在，批量菜单不应再给「Git 克隆…」「创建仓库…」
    for unwanted in ("Git 克隆…", "创建仓库…"):
        assert unwanted not in cmds, cmds
    states = 0
    for p in repos:
        states |= mi.compute_item_states(p, extended=False)
    assert states & mi.ITEMIS_INGIT, "两个仓库都应在版本控制内"
    dlg.reject()


def _submenu(menu, label):
    """按标题取子菜单（与 test_dialogs2.py 中的助手一致）。"""
    for act in menu.actions():
        sub = act.menu()
        if sub is not None and act.text() == label:
            return sub
    return None


def test_repo_context_menu_uses_tortoisegit_submenu(
        qapp, tmp_path, isolated_settings, monkeypatch):
    """仓库节点右键与目录树同构：第一层命令 + 「TortoiseGit」子菜单。

    第一层只保留勾选命令（同步/提交），克隆与创建仓库被排除；拉取/推送/
    仓库浏览器等进子菜单，与目录树仓库节点一致。
    """
    from PySide6.QtWidgets import QMenu

    repos = _make_repos(tmp_path, 3)
    dlg = _dlg_with(repos)
    tree = dlg.repo_tree

    captured = []
    monkeypatch.setattr(QMenu, "exec", lambda self, *a, **k: captured.append(self))

    def open_menu_for(item):
        captured.clear()
        tree.setCurrentItem(item)
        pos = tree.visualItemRect(item).center()
        dlg._on_repo_context_menu(pos)
        assert captured, "右键应构建菜单"
        return captured[-1]

    # ---- 单选：两层结构 ----
    menu = open_menu_for(tree.topLevelItem(0))
    tg = _submenu(menu, "TortoiseGit")
    assert tg is not None, [a.text() for a in menu.actions()]
    top_items = [a.text() for a in menu.actions() if a.text()]
    # 「提交…」带上目标分支（对齐原版 `Commit -> "master"...`）
    assert any(t.startswith("提交…") and "main" in t for t in top_items), top_items
    assert "同步" in top_items, top_items
    assert "从列表移除" in top_items, top_items
    for unwanted in ("拉取…", "推送…", "仓库浏览器", "Git 克隆…", "创建仓库…"):
        assert unwanted not in top_items, (unwanted, top_items)
    sub_labels = [a.text() for a in tg.actions() if a.text()]
    for expected in ("拉取…", "推送…", "差异…", "显示日志", "仓库浏览器"):
        assert expected in sub_labels, sub_labels
    commit_sub = [t for t in sub_labels if t.startswith("提交…")]
    if commit_sub:
        assert "main" in commit_sub[0], commit_sub

    # ---- 多选：追加批量操作 + 批量移除 ----
    tree.topLevelItem(0).setSelected(True)
    tree.topLevelItem(1).setSelected(True)
    tree.topLevelItem(2).setSelected(True)
    menu = open_menu_for(tree.topLevelItem(1))
    top_items = [a.text() for a in menu.actions() if a.text()]
    assert "打开 3 个仓库" in top_items, top_items
    assert "对选中的 3 个仓库运行…" in top_items, top_items
    assert "从列表移除 3 个仓库" in top_items, top_items
    # 批量运行子菜单仍与第一层同构（不含克隆/创建仓库）
    batch = _submenu(menu, "对选中的 3 个仓库运行…")
    assert batch is not None
    batch_labels = [a.text() for a in batch.actions() if a.text()]
    assert any(t.startswith("提交…") for t in batch_labels), batch_labels
    for unwanted in ("Git 克隆…", "创建仓库…"):
        assert unwanted not in batch_labels, batch_labels
    dlg.reject()


def test_commit_menu_shows_branch(qapp, repos, isolated_settings):
    """提交菜单显示提交到哪个分支（对齐原版 `Commit -> "branch"...`）。"""
    from pytortoisegit.git.git import GitRunner

    dlg = _dlg_with(repos)
    label = dlg._commit_label_with_branch("提交…", repos[0])
    assert label == '提交… -> "main"', label
    # 子目录 / 仓库根 都给同一分支
    sub = os.path.join(repos[0], "sub")
    os.makedirs(sub, exist_ok=True)
    assert dlg._commit_branch_name(sub) == "main"
    assert dlg._commit_branch_name(repos[0]) == "main"
    # 非仓库路径不追加后缀
    assert dlg._commit_branch_name(os.path.dirname(repos[0])) == ""
    assert dlg._commit_label_with_branch(
        "提交…", os.path.dirname(repos[0])) == "提交…"
    # 超长分支名按 64 字符截断
    long_branch = "feature/" + "b" * 70
    gr = GitRunner(cwd=repos[0])
    assert gr.run("checkout", "-q", "-b", long_branch).returncode == 0
    branch = dlg._commit_branch_name(repos[0])
    assert branch == long_branch[:64] + "...", branch
    assert dlg._commit_label_with_branch("提交…", repos[0]) == \
        '提交… -> "' + long_branch[:64] + '..."'
    dlg.reject()


def test_commit_label_shortens_detached_head(
        qapp, repos, isolated_settings, tmp_path):
    """分离头（HEAD 是完整 SHA1）在提交菜单里只显示前 8 位。"""
    from pytortoisegit.dialogs.mainmenu import MainMenuDlg
    from pytortoisegit.git.git import GitRunner

    det = tmp_path / "detached"
    gr = GitRunner(cwd=repos[0])
    assert gr.run("worktree", "add", "-q", "--detach", str(det)).returncode == 0
    sha = GitRunner(cwd=str(det)).run("rev-parse", "HEAD").stdout.strip()
    assert len(sha) == 40, sha

    dlg = _dlg_with(repos)
    assert dlg._commit_branch_name(str(det)) == sha[:8] + "..."
    assert dlg._commit_label_with_branch("提交…", str(det)) == \
        '提交… -> "' + sha[:8] + '..."'
    # 普通分支名不受影响
    assert dlg._shorten_sha1_ref("main") == "main"
    assert dlg._shorten_sha1_ref("feature/topic") == "feature/topic"
    dlg.reject()
