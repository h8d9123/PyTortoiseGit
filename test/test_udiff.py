"""udiff 解析测试。"""

from pytortoisegit.udiff import parse_diff, parse_file_patch


SAMPLE = """diff --git a/readme.txt b/readme.txt
index 9daeafb..a95bb45 100644
--- a/readme.txt
+++ b/readme.txt
@@ -1,3 +1,4 @@
 line1
-line2
 line3
+line new
+line4
"""

SAMPLE_NEWFILE = """diff --git a/new.txt b/new.txt
new file mode 100644
index 0000000000000000000000000000000000000000..1dab3ec 100644
--- /dev/null
+++ b/new.txt
@@ -0,0 +1 @@
+hello
"""

SAMPLE_RENAME = """diff --git a/old.py b/new.py
similarity index 100%
rename from old.py
rename to new.py
index aaaaaaa..bbbbbbb 100644
"""


def test_split_diff_multiple_files():
    data = SAMPLE + SAMPLE_NEWFILE
    patches = parse_diff(data)
    assert len(patches) == 2
    assert patches[0].new_path == "readme.txt"
    assert patches[1].new_path == "new.txt"


def test_hunk_counts_and_lines():
    patch = parse_file_patch(SAMPLE)
    assert patch is not None
    assert len(patch.hunks) == 1
    hunk = patch.hunks[0]
    assert hunk.old_start == 1 and hunk.new_start == 1
    assert hunk.added == 2
    assert hunk.removed == 1
    # 行号验证
    lines = hunk.lines
    assert lines[0].old_lineno == 1 and lines[0].new_lineno == 1   # context
    assert lines[1].is_deletion and lines[1].old_lineno == 2       # -line2
    assert lines[2].old_lineno == 3 and lines[2].new_lineno == 2   # context line3
    assert lines[3].is_addition and lines[3].new_lineno == 3       # +line new
    assert lines[4].is_addition and lines[4].new_lineno == 4       # +line4


def test_new_file_detection():
    patch = parse_file_patch(SAMPLE_NEWFILE)
    assert patch is not None
    assert patch.is_new
    assert patch.new_path == "new.txt"
    assert patch.old_path == "new.txt"
    assert patch.added == 1


def test_rename_detection():
    patch = parse_file_patch(SAMPLE_RENAME)
    assert patch is not None
    assert patch.is_rename
    assert patch.old_path == "old.py"
    assert patch.new_path == "new.py"


def test_line_for():
    patch = parse_file_patch(SAMPLE)
    ln = patch.line_for(3)
    assert ln is not None and ln.content == "line new"
    assert patch.line_for(99) is None


def test_filename_display_rename():
    patch = parse_file_patch(SAMPLE_RENAME)
    assert "→" in patch.filename_display
    assert patch.git_path == "new.py"
    assert patch.ext == ".py"
    assert patch.status_code == "R"


def test_new_file_status_and_ext():
    patch = parse_file_patch(SAMPLE_NEWFILE)
    assert patch.status_code == "A"
    assert patch.ext == ".txt"
    assert patch.git_path == "new.txt"


def test_empty_diff():
    assert parse_file_patch("") is None
    assert parse_diff("") == []


def test_binary_detection():
    binary = """diff --git a/x.png b/x.png
index aaa..bbb 100644
Binary files a/x.png and b/x.png differ
"""
    patch = parse_file_patch(binary)
    assert patch is not None
    assert patch.is_binary