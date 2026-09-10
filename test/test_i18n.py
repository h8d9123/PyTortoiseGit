"""i18n：tr() 按语言返回中/英文。"""

from pytortoisegit.res import strings


def test_language_switch():
    strings.set_language("zh")
    assert strings.get_language() == "zh"
    assert strings.tr("ok", "OK") == "确定"
    assert strings.tr("cancel", "Cancel") == "取消"

    strings.set_language("en")
    assert strings.get_language() == "en"
    assert strings.tr("ok", "OK") == "OK"
    assert strings.tr("cancel", "Cancel") == "Cancel"
    strings.set_language("zh")


def test_set_language_variants():
    strings.set_language("zh_CN")
    assert strings.get_language() == "zh"
    strings.set_language("English")
    assert strings.get_language() == "en"
    strings.set_language("Deutsch")
    assert strings.get_language() == "en"
    strings.set_language("zh_TW")
    assert strings.get_language() == "zh"
    strings.set_language("zh")


def test_tr_missing_key_falls_back():
    strings.set_language("zh")
    # 未登记的 key：中文回退 default
    assert strings.tr("__nope__", "Fallback") == "Fallback"
    strings.set_language("en")
    assert strings.tr("__nope__", "Fallback") == "Fallback"
    strings.set_language("zh")


def test_no_chinese_ui_literals():
    """UI 源码中不应再有中文文案（default 统一为英文，中文入 STRINGS）。

    白名单：语言下拉的本地化名称。
    """
    import ast
    import glob
    import os

    root = os.path.join(os.path.dirname(__file__), "..", "pytortoisegit")
    allowed = {"简体中文", "繁體中文"}
    offenders = []
    for path in glob.glob(os.path.join(root, "**", "*.py"), recursive=True):
        if path.endswith("strings.py"):
            continue
        src = open(path, encoding="utf-8").read()
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        docs = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                body = getattr(node, "body", [])
                if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                    docs.add(id(body[0].value))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                continue
            if id(node) in docs or node.value in allowed:
                continue
            if any("\u4e00" <= ch <= "\u9fff" for ch in node.value):
                offenders.append((os.path.relpath(path, root), node.lineno))
    assert not offenders, offenders[:30]
