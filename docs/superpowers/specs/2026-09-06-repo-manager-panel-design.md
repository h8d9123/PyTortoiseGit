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

菜单结构与目录树的仓库节点一致（**两层**）：勾选为「第一层」的命令留在顶层，
其余进「TortoiseGit」子菜单（`_add_tortoisegit_submenu`）。仓库已在磁盘上，
因此仓库管理面板的第一层排除 **Git Clone…** / **创建仓库…**
（`_REPO_MENU_EXCLUDE_TOP`）。

```python
def _on_repo_context_menu(self, pos):
    item = self.repo_tree.itemAt(pos)
    if item is None:
        return
    # 右键未选中项 → 重置为单选；右键已选中项 → 保留整个多选集合
    if not item.isSelected():
        self.repo_tree.clearSelection()
        self.repo_tree.setCurrentItem(item)
    selected = self._selected_repo_items()
    multi = len(selected) > 1
    if item.data(0, ROLE_KIND) == "repo":
        menu = QMenu(self.repo_tree)
        # 第一层（同步/提交…）+「TortoiseGit」子菜单（其余命令）
        self._add_tortoisegit_submenu(menu, item.data(0, ROLE_PATH),
                                      exclude_top=_REPO_MENU_EXCLUDE_TOP)
        if multi:
            self._add_multi_repo_actions(menu)     # 打开 N 个仓库 / 对 N 个仓库运行…
        menu.addSeparator()
        act_rem = menu.addAction("从列表移除")       # 多选时为「从列表移除 N 个仓库」
        act_rem.triggered.connect(
            lambda _=False, its=list(selected): self._remove_repos_from_list(its))
    else:
        # 子模块节点：仅「打开子模块」（多选时批量打开）
        ...
    menu.exec(self.repo_tree.viewport().mapToGlobal(pos))
```

多选（Ctrl/Shift）见 §13。

### 4.4 提交菜单显示目标分支（2026-09-10 追加）

对齐原版 `ContextMenu.cpp:529-587`：所有位置（仓库管理树 / 目录树 / 内容区 /
文件）的「提交…」菜单项都追加当前分支，提示提交到哪个分支：

```
提交… -> "master"
```

- `_commit_label_with_branch(label, path)`：取不到分支名时保持原标签；
  原名末尾的 `…` 会先去掉再拼后缀（对齐原版「先回退到 `...` 之前再拼接」）。
- **注意 `tr(key, default)` 的语义**（`res/strings.py:1868`）：中文界面下只要
  `STRINGS` 里有 key 就直接返回中文，**完全忽略 default**。所以动态后缀必须
  在 `tr()` 之后拼接；把改写过的文案当 default 传进 `tr()` 会被字典覆盖掉
  （此处踩过一次：菜单一直显示「提交…」，看不到分支）。
- `_commit_branch_name(path)`：文件取其所在目录；`_branch_of` 直接读
  `.git/HEAD`，不跑子进程。
- `分离头`（HEAD 是完整 SHA1）→ `_shorten_sha1_ref` 只显示前 8 位 + `...`；
  分支名超过 64 字符（`_COMMIT_BRANCH_MAX`）同样截断。
- 子模块节点的「提交子模块…」不加分支后缀（与原版一致）。
- 批量菜单（「对选中的 N 个仓库运行…」）不显示单个分支名，避免误导：各仓库
  分支在各自打开提交对话框时才显示。

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

---

## 10. 目录树标签页（2026-09-07 追加）

用户追加需求：**目录树需要，在另一个 tab 页**。恢复原「浏览文件夹」能力，
与仓库管理并存于左面板标签组。

### 布局

左面板由普通 `QWidget` 改为 `QTabWidget(manager_tabs)`：

```
manager_tabs
├─ Tab 0「仓库管理」repo_manager_panel（原有内容不变）
└─ Tab 1「目录树」folder_tree_panel
   ├─ QLabel("目录树")
   ├─ QTreeWidget folder_tree（单列、隐藏表头、SP_DirIcon/SP_DriveHDIcon）
   └─ QLabel("双击仓库目录打开；右键仓库目录可添加并执行操作")
```

视图菜单 `act_repo` 标题改为 `menu_left_panel`（"左侧面板"），控制
`self.manager_tabs.setVisible(on)`。

### 目录树行为

- **根节点**：磁盘分区（Windows 下探测 `A:\`~`Z:\` 存在的分区），非 Windows 为 `/`。
- **懒加载**：目录节点预挂一个 `placeholder` 子项，`itemExpanded` 时移除并调用
  `_load_dir_item` 列出直接子目录，`ROLE_LOADED` 标记避免重复加载。
- **仓库标记**：子目录用 `find_repo_root(sub) == os.path.abspath(sub)` 判定是否为
  **仓库工作树根**；是则 `ROLE_KIND="repo"` 并应用 `IDI_GITFOLDER` 图标，否则
  `ROLE_KIND="dir"` + `SP_DirIcon`。
- **双击**：仓库目录 → `open_repo(path)`；其余目录交给默认展开。
- **右键**：仓库目录 → 「添加到仓库管理」（`_ensure_in_repo_list`）+ 经典
  TortoiseGit 命令菜单（复用 `_CLASSIC_MENU`，与仓库管理 tab 共享）；非仓库目录无菜单。
- 加载失败（无权限等）静默跳过。

### 数据角色（沿用仓库管理树）

`ROLE_PATH`=绝对路径、`ROLE_KIND`∈{repo, dir, drive, placeholder}、
`ROLE_LOADED`=是否已加载下级。

### 新增文案键（`res/strings.py`）

```
"browser_tab_repo": "仓库管理",
"browser_tab_folder": "目录树",
"folder_hint": "双击仓库目录打开；右键仓库目录可添加并执行操作",
"menu_add_to_repo_list": "添加到仓库管理",
"menu_left_panel": "左侧面板",
```

### 命令分发的路径支持

`_dispatch` 原守卫要求「已打开仓库或路径行非空」。目录树右键针对**未打开**的仓库，
故守卫放宽为：`self.repo / path_row 非空 / extra 含 "path"` 任一成立即可执行；
`extra["path"]` 仍覆盖 `cl.options["path"]`。

### 测试要点（追加）

- 冒烟：`manager_tabs.count() == 2`、标签文案、`folder_tree.topLevelItemCount() >= 1`（存在磁盘）。
- 仓库标记与打开：构造「仓库根为某目录子项」的临时仓库，直接调用 `_load_dir_item`
  以快速定位（避免遍历真实磁盘），断言 `ROLE_KIND == "repo"`；`_on_folder_double_clicked`
  后 `repo.root == 仓库路径`。
- 添加到仓库管理：`_build_folder_repo_menu(path).actions()[0].trigger()`
  后 `path in _repo_list` 且 `repo_tree.topLevelItemCount() == 1`。

## 11. 目录树右键菜单（2026-09-07 追加）

按「是否 git 仓库」区分右键菜单：

### 非仓库目录（`ROLE_KIND` ∈ {dir, drive}）

- **Git Clone…**：打开 `CloneDlg`，默认目标目录 = 该目录。`clone.py` 的
  `CommandLine` 支持 `dir` 选项传入默认目录；`CloneDlg` 新增 `default_dir` 参数，
  构造时优先回填 `dir_edit`。
- **Settings**：`_dispatch("settings", extra={"path": 该目录})` —— settings 命令
  通过 `repo_from_cl_optional` 尽可能打开仓库配置；非仓库时为全局设置。

驱动 `_build_folder_nonrepo_menu(path)`。

### 仓库目录（`ROLE_KIND` == "repo"，参考 TortoiseGit）

`_build_folder_repo_menu(path)`：
- **添加到仓库管理**
- 分隔线 + 经典 TortoiseGit 命令（`_CLASSIC_MENU`）
- 分隔线 + **Settings**（`_dispatch("settings", extra={"path": path})`）

仓库管理 tab 的仓库节点右键（`_add_tortoisegit_submenu`）与目录树仓库节点同构：
第一层命令 + 「TortoiseGit」子菜单，同样含 **Settings**。

### 执行方式

clone/settings 是模态对话框命令，通过 `QTimer.singleShot(0, ...)` 异步调用
`_run(ctx, name)` → `dispatch`，避免阻塞 GUI 事件循环。

### 新增文案键

```
"repo_menu_clone": "Git Clone…",
"repo_menu_settings": "Settings",
```

### 测试要点（追加）

- `CloneDlg(default_dir=...)` 回填 `dir_edit`。
- `_build_folder_nonrepo_menu` 含 `Git Clone…` 与 `Settings`。
- `_build_folder_repo_menu` 首项为「添加到仓库管理」且含 `Settings`。
- 「刷新」：右键目录/分区/仓库节点均提供「刷新」（`_refresh_folder_item`），
  重新扫描直接子目录；展开节点立即重载，折叠节点重置占位子项延迟重载。

## 12. 目录树右键「刷新」（2026-09-07 追加）

目录/分区/仓库节点的右键菜单末尾均新增「刷新」，调用 `_refresh_folder_item(item)`：

```python
def _refresh_folder_item(self, item):
    # 清空子项 → 重置 ROLE_LOADED
    # 已展开：立即 _load_dir_item 重建
    # 未展开：重置占位子项（placeholder），下次展开时懒加载
```

仓库节点菜单（`_build_folder_repo_menu`）与目录节点菜单
（`_build_folder_nonrepo_menu`）均接收可选 `item` 参数，传入后追加「刷新」；
未传入（测试或纯命令场景）则不追加。

## 13. 右侧内容浏览面板（2026-09-07 追加，后改用 QFileSystemModel）

右侧「命令列表」替换为「内容浏览」区（资源管理器中间窗格风格）；命令入口
移至菜单栏「命令(&C)」（`_build_command_menu` + `MENU_GROUPS` 分组）。
已移除工具栏（TOOLBAR）与「视图→工具栏」开关（2026-09-09）。

`content_list` = `QTreeView` + `QFileSystemModel`（`fs_model`），仅显示名称列，
`setRootIsDecorated(False)`/`setItemsExpandable(False)` 关闭展开装饰。

行为：
- 单击左侧仓库管理树节点 → `_on_repo_clicked`：`path_row` 设为该仓库根，
  `_show_content(path)` 列出仓库根内内容。
- 单击左侧目录树节点 → `_on_folder_clicked`：`_show_content(path)`。
- `_show_content(path)`：`fs_model.setRootPath(abspath)` 后 `setRootIndex`，
  由模型自动列出子文件夹与文件（图标、排序由模型管理）。
- 图标：自定义 `_GitIconProvider(QFileIconProvider)`，仓库根目录显示
  `IDI_GITFOLDER`，其余交给系统默认图标。
- 右侧双击（`_on_content_double_clicked`）：任意目录（含仓库根）→ 进入浏览；
  文件 → 无操作。仓库不因双击直接打开，仓库操作通过右键菜单
  （`_build_classic_menu`）与「命令」菜单执行。
- 右侧右键（`_on_content_context_menu`）/ 目录树右键
  （`_on_folder_context_menu`）：用 `_inside_repo(path)` 判定——
  **工作树内任意位置**（`find_repo_root(path)` 非空，含仓库根与仓库内子目录）
  显示完整经典 TortoiseGit 菜单（`_build_classic_menu`，Commit/Log/Pull/Push/Sync/
  Revert/Clean Up + Settings）；仓库之外的目录显示 Clone… + Settings。
- 空白处右键（`_on_content_context_menu` / `_build_blank_menu`）：TortoiseGit 行为，
  对「当前浏览目录」弹**文件夹背景菜单**（`_BLANK_MENU`）——工作树内显示完整选项：
  Git Clone… / Pull… / Push… / Sync / Commit… / Diff… / Show log / Repo Browser /
  Stash changes… / Revert… / Switch/Checkout… / Merge… / Settings（参考
  TortoiseGit 文件夹空白菜单）；仓库外 → Clone…+Settings。目录/文件上右键仍弹
  item 对应菜单（`_CLASSIC_MENU`/文件菜单）。
- 文件右键（`_build_file_menu`）：系统「打开」（`QDesktopServices.openUrl`）
  与「显示位置」（explorer /select）；若文件位于工作树内，另附 TortoiseGit
  经典**已跟踪文件**菜单（参考 MenuInfo.cpp）：Commit… / Diff… / Show log /
  Stash changes… / Blame… / Settings（不含 Remove）。仓库外文件仅有系统项。
- 右键经 `_build_context_menu_for(index)`（仅构建）与 `_show_context_menu_for`
  （构建+exec）显示菜单：文件→文件菜单；工作树内目录→经典菜单；其余→Clone+Settings。
- commit 命令（commands/commit.py）现在透传文件路径给 CommitDlg(paths=)。
- 底部「打开/关于/关闭」按钮已移除（2026-09-09）：双击与右键覆盖全部操作，
  「关于」在菜单栏帮助菜单，「关闭」用窗口标题栏/任务栏按钮。
- 导航行（Windows 资源管理器风格）：后退 `btn_back`(←)、前进
  `btn_forward`(→)、向上 `btn_up`(↑)、刷新 `btn_refresh`(⟳)。
  - `_navigate(path)`：进入目录并把当前压入后退栈、清空前栈（后退可回退）。
  - `_go_back` / `_go_forward`：在后退/前进栈间移动。
  - `_go_up`：进入父目录（纳历史）；也通过 `_navigate`。
  - `_refresh_content`：重扫当前目录（不改变历史）。
  - `_current_dir()` 返回当前浏览目录。
  - 左侧单击 / 右侧双击进入目录均走 `_navigate`，支持后退/前进。
  - `_update_nav_buttons()` 按栈状态启停后退/前进按钮。

> 注：`QFileSystemModel` 为异步后台填充，切换路径后需短时等待其扫描完成。

### 新增文案键

```
"menu_open_content": "打&开",
"content_hint": "单击左侧目录/仓库查看子文件夹；双击进入或打开",
"file_menu_open": "打开",
"file_menu_show_in": "显示位置",
"file_menu_tg": "TortoiseGit",
"file_menu_diff": "与 HEAD 比较（Diff）…",
"file_menu_blame": "追溯（Blame）…",
"file_menu_log": "显示日志（Log）…",
"file_menu_remove": "删除（Remove）…",
"menu_commands": "命令(&C)",
"menu_grp_changes": "本地更改",
"menu_grp_inspect": "查看/比较",
"menu_grp_syncing": "获取/发布",
"menu_grp_branch": "分支/合并",
"menu_grp_clone": "仓库",
"menu_grp_format": "补丁/导出",
"menu_grp_utils": "工具/其他",
"menu_grp_other": "其他",
（`menu_cmd_<name>`：各命令显示名）
```

### 命令菜单

- 菜单栏在「视图」与「帮助」间新增「命令(&C)」(`menu_commands`)。
- `_build_command_menu(m_cmd)`：调用 `_ensure_imports()` 后遍历
  `available_commands()`，按 `MENU_GROUPS`（类常量：组名 → 命令列表）归入
  各分组子菜单；未归类的命令放入「其他」。
- 标签：`tr("menu_cmd_" + name, name)`（有映射则显示友好名，否则为命令名）。
- 所有菜单项触发 `_dispatch(name)`（与工具栏一致，作用于当前 `path_row`）。

### 右键菜单图标（2026-09-09 追加）

- 图标与 TortoiseGit 一致：`scripts/sync_icons.py` 现同时扫描
  `TortoiseGit-master/src/Resources` 与 `src/TortoiseShell`（`resourceshell.rc`），
  生成 `res/icon_map.py`（IDI_* → menu*.ico）。共 141 个图标、149 条映射。
- mainmenu.py 定义 `_CMD_ICON`：命令名 → TGit 菜单图标 ID（如
  commit→IDI_COMMIT=menucommit.ico、log→IDI_LOG=menulog.ico、
  pull→IDI_PULL=pull1.ico、push→IDI_PUSH=Push.ico、sync→IDI_RELOCATE、
  revert→IDI_REVERT、cleanup→IDI_CLEANUP、diff→IDI_DIFF=menucompare.ico、
  stash→IDI_SHELVE、blame→IDI_BLAME、settings→IDI_SETTINGS=menusettings.ico）。
- `_set_action_icon(action, icon_id)` 为动作设图标；`_build_classic_menu`、
  `_build_file_menu`、`_build_context_menu_for`、`_build_command_menu`、
  `_build_folder_repo_menu`、`_build_folder_nonrepo_menu` 均已为 Git 命令项加图标。

### 测试要点（追加）

- `test_mainmenu_dialog`：`content_list` 存在，且窗口无工具栏（`findChild(QToolBar) is None`）。
- `test_mainmenu_content_shows_subfolders`：`_show_content` 后 `rowCount==3`
  （plain/innerrepo/b.txt），innerrepo 识别为仓库根。
- `test_mainmenu_content_double_click_repo_enters`：双击仓库内容节点 → 进入
  浏览（`_current_dir` 变为仓库路径，`repo` 不打开）。
- `test_mainmenu_file_menu_includes_tg_commands` / `test_mainmenu_file_menu_outside_repo_only_system`：
  文件右键菜单——工作树内文件含打开/显示位置 + Commit/Diff/Log/Stash/Blame/
  Settings（无 Remove）；仓库外文件仅系统项。
- `test_mainmenu_command_menu_lists_all_commands`：命令菜单含全部分组
  （本地更改/其他等），且每个 `available_commands()` 的命令均有对应菜单项。
- `test_mainmenu_menu_actions_have_tortoisegit_icons`：经典菜单
  （Commit/Log/Pull/Push/Sync/Revert/CleanUp/Settings）、文件菜单
  （打开/Commit/Diff/Show log/Stash/Blame/Settings）、仓库外目录
  （Clone/Settings）各项 `icon().isNull()` 均为 False。
- `test_mainmenu_blank_area_context_menu_uses_current_dir`：内容区空白处右键
  对当前浏览目录弹菜单——工作树内含完整选项
  （Clone/Pull/Push/Sync/Commit/Diff/Show log/Repo Browser/Stash changes/Revert/
  Switch・Checkout/Merge/Settings）；仓库外仅 Clone+Settings。

> 时序：模型异步填充，测试用 `QTest.qWait` 轮询 `rowCount>0` 后再断言。

## 13. 仓库管理面板多选（2026-09-10 追加）

`repo_tree` 启用 `ExtendedSelection` + `SelectRows`：Ctrl 点选、Shift 连选、
空白处拖拽框选（与右侧内容区一致）。

### 选中集合

- `_selected_repo_items()`：按树中顺序返回选中节点（顶层仓库 + 其子模块）。
- `_selected_repo_paths()`：折算为仓库根路径（子模块取 `ROLE_PARENT`），去重。
- `_selected_repo_roots()`：跳过子模块节点，供批量命令使用。
- `_multi_selected()`：选中节点 > 1。

### 行为

- **状态栏/提示**：多选时状态栏显示「已选中 N 个仓库 · 首个路径」，
  欢迎区显示「已选中 N 项」；回到单选/空选恢复原文案。
- **单击**：多选状态下不切换右侧内容（避免连选时内容区反复跳转）。
- **重建树**：`_refresh_repo_tree` 在 `clear()` 前记下选中路径，重建后恢复；
  仅当原本无选中项时才把当前仓库设为默认选中。
- **右键**：未选中项 → 重置为单选；已选中项 → 保留整个多选集合。
  多选时追加「打开 N 个仓库」「对选中的 N 个仓库运行…」（
  `_populate_batch_menu` 取各仓库 `itemStates` 的**并集**，`_dispatch_each`
  对每个仓库各分发一次），「从列表移除」变为批量移除
  （`_remove_repos_from_list`）。

### 测试要点（追加）

- `test_repo_tree_supports_ctrl_shift_multiselect`：选择模式 + 追加选中 → 路径集合。
- `test_repo_multiselect_status_and_content`：多选时状态栏计数、内容区不跳转。
- `test_repo_tree_keeps_selection_after_refresh`：重建树后选中保持。
- `test_repo_multiselect_remove_all`：批量移除并落盘 QSettings。
- `test_repo_multiselect_actions_apply_to_all`：批量打开 + 批量命令分发到每个仓库。
- `test_repo_batch_menu_merges_states`：批量菜单按状态并集生成。
- `test_repo_context_menu_uses_tortoisegit_submenu`：第一层命令与
  「TortoiseGit」子菜单分层，顶层无克隆/创建仓库。
