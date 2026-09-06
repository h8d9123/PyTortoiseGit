# 主窗口「仓库管理」面板设计

日期：2026-09-06
状态：已确认

## 背景

主窗口左侧原为「子模块树」。用户希望用「仓库管理」列表替代，支持同时管理多个 Git 仓库（每个仓库下可展开子模块），并提供 TortoiseGit 经典右键菜单。

## 目标

- 左侧替换为 `仓库管理列表`（仓库为顶层节点，子模块为其子项）
- 打开仓库（路径行回车 / 菜单「打开仓库」）时自动把该仓库加入管理列表
- 右键仓库节点 → 经典 TortoiseGit 菜单 + 「从列表移除」
- 双击仓库节点 → 主窗口切换到该仓库；双击子模块 → 打开子模块窗口
- 已添加的仓库路径持久化到 QSettings（跨重启保留）

---

## 1. 布局改动（`dialogs/mainmenu.py`）

`_build_central` 原先创建 `sub_module_dock`（内含标题 `QLabel` + `sub_tree` + 提示 `QLabel`）。改为：

```
仓库管理面板 QWidget
├─ QLabel("仓库管理")                      # 标题
├─ QTreeWidget                             # 列表主控件
└─ QLabel("双击仓库切换；展开可查看子模块")  # 底部提示
```

保留 `split` 的两个 widget（左侧新面板 / 右侧命令区）+ 现有 Stretch 与 `splitSizes`。

**移除**：原 `_load_submodules`、`_on_submodule_open`、`sub_tree` 相关字段。
**新增**：
- `self.repo_tree: QTreeWidget` — 仓库管理树（顶层为仓库节点，子项为子模块）
- `self._repo_list: list[str]` — 内存中的仓库路径列表（与 QSettings 同步）

## 2. 数据持久化（QSettings）

沿用现有 `general_settings()` → `QSettings("PyTortoiseGit", "PyTortoiseGit")`。

| 键                 | 类型       | 说明                     |
|--------------------|-----------|--------------------------|
| `Browser/Repos`   | QStringList | 已添加仓库的根目录路径列表 |

### 操作

```python
from ..settingsdlg import general_settings
_KEY_REPOS = "Browser/Repos"

def _load_repo_list(self) -> list[str]:
    return general_settings().value(_KEY_REPOS, [], type=list)

def _save_repo_list(self):
    general_settings().setValue(_KEY_REPOS, self._repo_list)
```

**刷新树**：读 `_repo_list` → 每个路径建顶层节点（文本为路径名；`UserRole` 存完整路径）→ 展开按钮触发懒加载子模块。

## 3. 自动加入管理列表

在 `open_repo(path)` 成功后（`self.repo` 已赋值），调用：

```python
def _ensure_in_repo_list(self, path: str):
    norm = os.path.normcase(os.path.abspath(path))
    if norm not in {os.path.normcase(p) for p in self._repo_list}:
        self._repo_list.append(norm)
        self._save_repo_list()
    self._refresh_repo_tree()
```

`_refresh_repo_tree` 重建树（清空 → 逐条路径建节点；对当前 repo 节点设置展开状态）。

## 4. 树控件行为

`repo_tree` 树属性：
- `setHeaderLabels(["路径", "状态", "SHA"])`，与现有子模块树一致的三列
- `setRootIsDecorated(True)`（有展开按钮）
- 双击信号 → `_on_repo_double_clicked`（统一处理仓库/子模块）
- 展开信号 `itemExpanded` → `_on_item_expanded`（懒加载子模块）
- 右键 → `_on_repo_context_menu`

### 4.1 子模块懒加载

仓库节点展开时（`itemExpanded`）首次调用 `GitSubmodule(repo).list()`，在子项处填子模块。用 `setData` 存路径与父仓库路径，重复展开不再重载。

子模块条目需存两个 UserRole：`UserRole` 存子模块的**完整绝对路径**（由父仓库根 + 子模块相对路径拼接），`UserRole+1` 存标记（`"submodule"`），并额外存父仓库根路径到 `UserRole+2`（供右键菜单使用）。

```python
def _on_item_expanded(self, item):
    if item.data(0, Qt.ItemDataRole.UserRole + 1) == "loaded":
        return
    repo_path = item.data(0, Qt.ItemDataRole.UserRole)
    if not repo_path:
        return
    try:
        from ..git.repo import Repository
        from ..git.submodule import GitSubmodule
        repo = Repository.open(repo_path)
        for e in GitSubmodule(repo).list(recursive=False):
            sub_abs = os.path.normpath(os.path.join(repo_path, e.path))
            sub = QTreeWidgetItem([e.path, e.status_text, (e.sha1 or "")[:8]])
            sub.setData(0, Qt.ItemDataRole.UserRole, sub_abs)
            sub.setData(0, Qt.ItemDataRole.UserRole + 1, "submodule")
            sub.setData(0, Qt.ItemDataRole.UserRole + 2, repo_path)
            item.addChild(sub)
    except Exception:
        pass
    item.setData(0, Qt.ItemDataRole.UserRole + 1, "loaded")
```

### 4.2 双击（统一处理：仓库 / 子模块）

```python
def _on_repo_double_clicked(self, item, _col):
    marker = item.data(0, Qt.ItemDataRole.UserRole + 1)
    if marker == "submodule":
        # 子模块：打开子模块管理窗口
        sub_path = item.data(0, Qt.ItemDataRole.UserRole)
        self._run_async_command("submodule", extra={"path": sub_path})
    else:
        # 仓库节点：切换主窗口
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path:
            self.open_repo(path)
```

### 4.3 右键菜单

```python
def _on_repo_context_menu(self, pos):
    item = self.repo_tree.itemAt(pos)
    if item is None:
        return
    from PySide6.QtWidgets import QMenu
    menu = QMenu(self.repo_tree)
    if item.parent() is None:
        # 仓库节点：经典 TortoiseGit 菜单 + 「移除」
        for cmd, label in [
            ("commit", "Commit…"),
            ("log", "Show log"),
            ("pull", "Pull…"),
            ("push", "Push…"),
            ("sync", "Sync"),
            ("revert", "Revert…"),
            ("cleanup", "Clean Up…"),
        ]:
            act = menu.addAction(label)
            act.triggered.connect(lambda _=False, c=cmd, p=item.data(0, Qt.ItemDataRole.UserRole):
                                  self._dispatch(c, extra={"path": p}))
        menu.addSeparator()
        act_rem = menu.addAction("从列表移除")
        act_rem.triggered.connect(lambda _=False, it=item: self._remove_repo_from_list(it))
    else:
        # 子模块节点：仅「打开子模块」
        sub_path = item.data(0, Qt.ItemDataRole.UserRole)  # 绝对路径
        act = menu.addAction("打开子模块")
        act.triggered.connect(lambda _=False, p=sub_path:
                              self._run_async_command("submodule", extra={"path": p}))
    menu.exec(self.repo_tree.viewport().mapToGlobal(pos))

def _remove_repo_from_list(self, item):
    path = item.data(0, Qt.ItemDataRole.UserRole)
    norm = os.path.normcase(os.path.abspath(path))
    self._repo_list = [p for p in self._repo_list if os.path.normcase(os.path.abspath(p)) != norm]
    self._save_repo_list()
    self._refresh_repo_tree()
```

## 5. 菜单/状态栏文案

在 `res/strings.py` 的 `STRINGS` 字典新增：

```python
"repo_manager_title": "仓库管理",
"repo_manager_hint": "双击仓库切换；展开可查看子模块",
"repo_menu_commit": "Commit…",
"repo_menu_log": "Show log",
"repo_menu_pull": "Pull…",
"repo_menu_push": "Push…",
"repo_menu_sync": "Sync",
"repo_menu_revert": "Revert…",
"repo_menu_cleanup": "Clean Up…",
"repo_menu_remove": "从列表移除",
"repo_menu_open_sub": "打开子模块",
```

提示：菜单项显示文本仍硬编码为 TortoiseGit 原文（`"Commit…"` 等），`tr()` 用于未来 i18n 支持；若仅需显示英文可直接用字面值，文案键仅存档。

## 6. 错误处理

- `open_repo(path)` 失败时（路径不是 git 仓库）：已保留现有行为（设置状态提示 `self.status.setText(...)`），不写入列表。
- QSettings 中有失效路径：`_load_repo_list` 时尝试 `Repository.open(path)`；失败的条目静默跳过，并在下次 `_save_repo_list` 时清除。
- 子模块加载失败：静默（`pass`），子项不出现。

## 7. 视图菜单适配

`_build_menu` 中视图菜单原本有 `act_sub`（子模块面板）控制 `self.sub_module_dock.setVisible(on)`。改为控制 `self.repo_manager_panel.setVisible(on)`，`act_sub` 标题改为 `tr("menu_repo_manager", "仓库管理面板")`。

## 8. 测试要点（`test/test_dialogs2.py`）

- **持久化**：使用 `QSettings` mock/monkeypatch 验证 `_save_repo_list` / `_load_repo_list`（或写临时路径后清理）。
- **自动加入**：`open_repo` 成功后 `_repo_list` 包含该路径；重复打开同一仓库不重复添加。
- **子模块懒加载**：用构造含 `.gitmodules` 的临时仓库（`git submodule add` 需要两个仓库，可用 stub 替代 mock `GitSubmodule.list`），验证展开后 `item.childCount() == 1`。
- **移除**：调用 `_remove_repo_from_list` 后列表长度减 1。
- **双击切仓库**：`open_repo` hook 捕获确认路径正确。
- 冒烟：`_smoke(qapp, lambda: MainMenuDlg(repo_path=...))` 确认无崩溃。

## 9. 实施顺序

1. `res/strings.py` 新增文案键
2. `dialogs/mainmenu.py` 改造：替换 `sub_module_dock` → `repo_manager_panel`；新增 `_repo_list`、`_load_repo_list`、`_save_repo_list`、`_ensure_in_repo_list`、`_refresh_repo_tree`、`_on_repo_double_clicked`（含子模块双击）、`_on_item_expanded`、`_on_repo_context_menu`、`_remove_repo_from_list`
3. 适配视图菜单
4. `test/test_dialogs2.py` 新增上述测试
5. 全量 `pytest test/` 回归
6. 提交（`feat: 主窗口左侧仓库管理面板`）
