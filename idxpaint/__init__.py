"""Indexed-colour painting kernel."""

from .brush import AlphaPolicy, Brush, LockPolicy, Ramp
from .canvas import IndexedCanvas
from .dither import OrderedDither
from .engine import PaintEngine, boundary_stripe_pollution
from .palette import Palette, PaletteEntry
from .png_codec import read_png, write_png
from .reorder import reorder_palette
from .storage import load_project, save_project

__all__ = [
    "AlphaPolicy",
    "Brush",
    "LockPolicy",
    "Ramp",
    "IndexedCanvas",
    "OrderedDither",
    "PaintEngine",
    "boundary_stripe_pollution",
    "Palette",
    "PaletteEntry",
    "read_png",
    "write_png",
    "reorder_palette",
    "load_project",
    "save_project",
]
