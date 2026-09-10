"""Patch 解析/应用 与 WorkingFile 属性。"""

import os

import pytest

from pytortoisegit.git.git import GitRunner
from pytortoisegit.git.repo import Repository
from pytortoisegit.merge.patch import Patch
from pytortoisegit.merge.workingfile import WorkingFile

DIFF = """diff --git a/a.txt b/a.txt
index 0000000..1111111 100644
--- a/a.txt
+++ b/a.txt
@@ -1,2 +1,3 @@
 line1
+inserted
 line2
"""


def test_patch_parse():
    p = Patch()
    assert p.parse_text(DIFF)
    assert p.get_number_of_files() == 1
    assert p.get_filename(0) == "a.txt"
    assert p.get_filename2(0) == "a.txt"


def test_check_patch_path():
    assert Patch.check_patch_path("dir/file.txt") == "dir/file.txt"
    assert Patch.check_patch_path("C:/abs/file.txt") == ""
    assert Patch.check_patch_path("/abs/file.txt") == ""
    assert Patch.check_patch_path("../up/file.txt") == ""


def test_count_matches():
    p = Patch()
    p.parse_text(DIFF)
    assert p.count_matches("a.txt") == 1
    assert p.count_matches("other.txt") == 0


def test_has_unicode_bom():
    assert Patch.has_unicode_bom("\ufeffabc")
    assert not Patch.has_unicode_bom("abc")
    assert Patch.remove_unicode_bom("\ufeffabc") == "abc"


def test_apply_patch(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    runner = GitRunner(cwd=str(root))
    runner.init(str(root), initial_branch="main")
    runner.run("config", "user.email", "t@x.com")
    runner.run("config", "user.name", "T")
    runner.run("config", "core.autocrlf", "false")
    (root / "a.txt").write_bytes(b"line1\nline2\n")
    runner.run("add", "-A")
    runner.run("commit", "-m", "init")
    repo = Repository.open(str(root))

    p = Patch(repo)
    assert p.apply_patch(DIFF, strip=1) == 0
    assert (root / "a.txt").read_bytes() == b"line1\ninserted\nline2\n"


def test_workingfile_attributes(tmp_path):
    f = tmp_path / "x.txt"
    f.write_text("a\n", encoding="utf-8")
    wf = WorkingFile()
    wf.set_file_name(str(f))
    wf.store_file_attributes()
    assert not wf.has_source_file_changed()
    # 修改文件 → 检测到变化
    import time
    time.sleep(0.01)
    f.write_text("b\n", encoding="utf-8")
    os.utime(str(f), None)
    assert wf.has_source_file_changed()
    wf.clear_stored_attributes()
    assert not wf.has_source_file_changed()
