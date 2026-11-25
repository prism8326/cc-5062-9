"""Shared test fixtures."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from idxpaint.brush import AlphaPolicy, Brush, LockPolicy, Ramp
from idxpaint.canvas import IndexedCanvas
from idxpaint.palette import Palette, PaletteEntry


def make_canvas(w: int = 32, h: int = 24, transparent: int = 0) -> IndexedCanvas:
    # Note entries 1 and 6 share RGB but are distinct indices; 0 is transparent.
    palette = Palette([
        PaletteEntry(0, 0, 0, 0, "transparent"),
        PaletteEntry(20, 20, 30, 255, "dark"),
        PaletteEntry(80, 80, 120, 255, "mid"),
        PaletteEntry(140, 140, 190, 255, "light"),
        PaletteEntry(210, 210, 235, 255, "pale"),
        PaletteEntry(220, 50, 50, 255, "accent"),
        PaletteEntry(20, 20, 30, 255, "dark-duplicate"),
        PaletteEntry(40, 150, 90, 255, "green"),
    ])
    return IndexedCanvas(w, h, palette, transparent_index=transparent)


def ink_ramp() -> Ramp:
    return Ramp((1, 2, 3, 4))


def make_brush(**kw) -> Brush:
    defaults = dict(ramp=ink_ramp(), radius=2.0, spacing=1.0, dither_order=3)
    defaults.update(kw)
    return Brush(**defaults)


def tmp_png() -> str:
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    return path


def tmp_project() -> str:
    d = tempfile.mkdtemp()
    return os.path.join(d, "project")
