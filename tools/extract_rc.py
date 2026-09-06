"""从 TortoiseGit 源目录提取全部对话框模板到 res/rc_dialogs.json。

用法：python tools/extract_rc.py <TortoiseGit源目录>
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pytortoisegit.ui import rc  # noqa: E402


def main() -> int:
    src = sys.argv[1] if len(sys.argv) > 1 else \
        r"D:\work\ai\TortoiseGit-master\TortoiseGit-master"
    rc_path = os.path.join(src, "src", "Resources", "TortoiseProcENG.rc")
    text = open(rc_path, encoding="utf-8-sig").read()
    dialogs = rc.parse_all(text)

    data = []
    for dlg in dialogs.values():
        data.append({
            "id": dlg.id,
            "w": dlg.width,
            "h": dlg.height,
            "caption": dlg.caption,
            "font": dlg.font,
            "font_size": dlg.font_size,
            "style": dlg.style,
            "controls": [
                {"k": c.kind, "t": c.text, "id": c.ctrl_id, "c": c.cls,
                 "s": c.style, "x": c.x, "y": c.y, "w": c.w, "h": c.h,
                 "ex": c.ex_style, "hidden": c.hidden}
                for c in dlg.controls],
        })

    out = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "pytortoisegit", "res", "rc_dialogs.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"written {len(data)} dialogs -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())