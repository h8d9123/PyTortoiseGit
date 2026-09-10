"""DiffColors 配色对齐 DiffColors.h 默认值。"""

from pytortoisegit.merge.diffcolors import DiffColors
from pytortoisegit.merge.viewdata import DiffState


def _rgb(color):
    return (color.red(), color.green(), color.blue())


def test_light_colors_match_diffcolors_h():
    c = DiffColors()
    assert _rgb(c.back_color(DiffState.Normal)) == (255, 255, 255)
    assert _rgb(c.back_color(DiffState.Removed)) == (255, 200, 100)
    assert _rgb(c.back_color(DiffState.Added)) == (255, 255, 0)
    assert _rgb(c.back_color(DiffState.Empty)) == (200, 200, 200)
    assert _rgb(c.back_color(DiffState.Conflict)) == (255, 100, 100)
    assert _rgb(c.back_color(DiffState.MovedFrom)) == (255, 200, 100)
    assert _rgb(c.back_color(DiffState.MovedTo)) == (255, 255, 0)
    assert _rgb(c.back_color(DiffState.ConflictsResolved)) == (200, 255, 200)
    assert _rgb(c.back_color(DiffState.Edited)) == (220, 220, 255)
    assert _rgb(c.back_color(DiffState.Filtered)) == (220, 255, 220)


def test_dark_colors_match_diffcolors_h():
    c = DiffColors(dark=True)
    assert _rgb(c.back_color(DiffState.Removed)) == (83, 66, 33)
    assert _rgb(c.back_color(DiffState.Added)) == (83, 83, 0)
    assert _rgb(c.back_color(DiffState.Empty)) == (66, 66, 66)
    assert _rgb(c.back_color(DiffState.Conflict)) == (83, 33, 33)
    assert _rgb(c.back_color(DiffState.Edited)) == (80, 80, 103)
    assert _rgb(c.back_color(DiffState.Filtered)) == (73, 83, 73)
    assert _rgb(c.back_color(DiffState.ConflictsResolved)) == (66, 83, 66)


def test_inline_colors_match_diffcolors_h():
    c = DiffColors()
    assert _rgb(c.inline_added_color()) == (255, 255, 150)
    assert _rgb(c.inline_removed_color()) == (200, 100, 100)
    cd = DiffColors(dark=True)
    assert _rgb(cd.inline_added_color()) == (120, 120, 50)
    assert _rgb(cd.inline_removed_color()) == (100, 40, 40)
