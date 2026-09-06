"""TGitPath 路径工具测试。"""

import os

import pytest

from pytortoisegit.utils.paths import TGitPath, is_valid_filename, validate_path_for_git


def test_basename():
    assert TGitPath(r"D:\repo\file.txt").filename == "file.txt"
    assert TGitPath("/repo/file.txt").filename == "file.txt"
    assert TGitPath("D:\\repo\\").filename == "repo"


def test_dirname_handles_trailing_separator():
    # SDirectoryName 语义：路径以分隔符结尾时也取父目录
    assert TGitPath("D:/repo/sub/").dirname == "D:/repo"


def test_forward_backslash_convert():
    p = TGitPath(r"D:\repo\a\b")
    assert p.to_forward() == "D:/repo/a/b"
    assert p.to_backslash() == "D:\\repo\\a\\b"


def test_is_child_of():
    p = TGitPath(r"D:\repo\sub\file.txt")
    assert p.is_child_of(r"D:\repo")
    assert not p.is_child_of(r"D:\repo\sub\file.txt")
    assert not p.is_child_of(r"D:\repo\other")


def test_relative_to():
    p = TGitPath(r"D:\repo\sub\file.txt")
    assert p.relative_to(r"D:\repo") == os.path.join("sub", "file.txt")


def test_join_operator():
    p = TGitPath("D:/repo") / "src" / "main.py"
    assert p.full == os.path.join("D:/repo", "src", "main.py")


def test_extension():
    assert TGitPath("a.tar.gz").extension == ".gz"
    assert TGitPath("noext").extension == ""


def test_valid_filename():
    assert is_valid_filename("normal.txt")
    assert not is_valid_filename("")
    assert not is_valid_filename(".")
    assert not is_valid_filename("con")          # Windows 保留名
    assert not is_valid_filename("a/b.txt")      # 非法字符
    assert not is_valid_filename("trailing. ")   # 尾随空格


def test_validate_path():
    assert validate_path_for_git("normal.txt") is None
    assert validate_path_for_git("a<b.txt") is not None


def test_is_same_ignores_case_windows():
    p1 = TGitPath(r"c:\Repo\A")
    p2 = TGitPath(r"C:\repo\a")
    if os.name == "nt":
        assert p1.is_same(p2)