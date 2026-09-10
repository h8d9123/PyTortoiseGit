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


def test_tr_missing_key_falls_back():
    strings.set_language("zh")
    # 未登记的 key：中文回退 default
    assert strings.tr("__nope__", "Fallback") == "Fallback"
    strings.set_language("en")
    assert strings.tr("__nope__", "Fallback") == "Fallback"
    strings.set_language("zh")
