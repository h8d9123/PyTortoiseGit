"""FileTextLines：编码检测（CheckUnicodeType）与 Load/Save。"""

import codecs
import os

from pytortoisegit.merge.filetextlines import (
    FileTextLines, UnicodeType, check_unicode_type,
)
from pytortoisegit.merge.eol import EOL


def test_check_unicode_type():
    assert check_unicode_type(b"hello\nworld\n") == UnicodeType.ASCII
    assert check_unicode_type("h\u00e9llo\n".encode("utf-8")) == UnicodeType.UTF8
    assert check_unicode_type(b"\xef\xbb\xbfhello\n") == UnicodeType.UTF8BOM
    assert check_unicode_type("h\u00e9llo\n".encode("utf-16-le")) == UnicodeType.UTF16_LE
    assert check_unicode_type("h\u00e9llo\n".encode("utf-16")) == UnicodeType.UTF16_LEBOM
    assert check_unicode_type("h\u00e9llo\n".encode("utf-16-be")) == UnicodeType.UTF16_BE
    assert check_unicode_type(codecs.BOM_UTF32_LE + "hi".encode("utf-32-le")) == UnicodeType.UTF32_LE
    assert check_unicode_type(codecs.BOM_UTF32_BE + "hi".encode("utf-32-be")) == UnicodeType.UTF32_BE
    # 完整 0x00000000 dword → 二进制
    assert check_unicode_type(b"abcd\x00\x00\x00\x00") == UnicodeType.BINARY


def test_load_detects_type_and_eol(tmp_path):
    p = tmp_path / "t.txt"
    p.write_bytes(b"\xef\xbb\xbf" + "line1\r\nline2\r\n".encode("utf-8"))
    ft = FileTextLines()
    assert ft.load(str(p))
    assert ft.unicode_type == UnicodeType.UTF8BOM
    assert ft.line_endings == EOL.CRLF
    assert ft.get_count() == 2
    assert [f.text for f in ft._vec] == ["line1", "line2"]
    assert [f.eol for f in ft._vec] == [EOL.CRLF, EOL.CRLF]


def test_load_utf16(tmp_path):
    p = tmp_path / "u16.txt"
    p.write_bytes("a\nb\n".encode("utf-16"))
    ft = FileTextLines()
    assert ft.load(str(p))
    assert ft.unicode_type == UnicodeType.UTF16_LEBOM
    assert [f.text for f in ft._vec] == ["a", "b"]


def test_save_roundtrip(tmp_path):
    p = tmp_path / "t.txt"
    p.write_bytes(b"\xef\xbb\xbf" + "l1\r\nl2\r\n".encode("utf-8"))
    ft = FileTextLines()
    ft.load(str(p))
    out = tmp_path / "out.txt"
    assert ft.save(str(out))
    assert out.read_bytes() == b"\xef\xbb\xbfl1\r\nl2\r\n"


def test_binary_file_errors(tmp_path):
    p = tmp_path / "b.bin"
    p.write_bytes(b"abcd\x00\x00\x00\x00efgh")
    ft = FileTextLines()
    assert not ft.load(str(p))
    assert ft.error_string
