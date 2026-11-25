"""Indexed-colour painting kernel."""

from .brush import AlphaPolicy, Brush, LockPolicy, Ramp
from .canvas import IndexedCanvas
from .diffusion import (
    DiffusionCursor,
    DiffusionSnapshot,
    ErrorPropagationCursor,
    ErrorSnapshot,
    ErrorState,
    ResidualSnapshot,
    ResidualState,
)
from .dither import DitherDecision, DitherPlanner, DitherStrategy, OrderedDither
from .engine import PaintEngine, boundary_stripe_pollution
from .evidence import collect_index_evidence, mapped_indices_equal
from .history import (
    ColorIndexMappingSnapshot,
    History,
    HistoryEntry,
    HistoryManager,
    IndexMappingSnapshot,
    PaintHistory,
    SnapshotHistory,
    UndoHistory,
    UndoManager,
)
from .index_canvas import CanvasSnapshot, IndexCanvas, IndexCanvasSnapshot, IndexSnapshot
from .palette import (
    Palette,
    PaletteDisplay,
    PaletteEntry,
    PaletteSnapshot,
    PaletteView,
    build_export_mapping,
    export_mapping,
)
from .painting import IndexPaintApp, IndexPainting, create_index_painting
from .palettes import PALETTE_TABLES, get_palette_table
from .png_codec import read_png, write_png
from .reorder import reorder_palette
from .storage import load_project, save_project

ColorRamp = Ramp
PaletteRamp = Ramp

__all__ = [
    "AlphaPolicy",
    "Brush",
    "LockPolicy",
    "Ramp",
    "ColorRamp",
    "PaletteRamp",
    "IndexCanvas",
    "IndexSnapshot",
    "IndexCanvasSnapshot",
    "CanvasSnapshot",
    "IndexedCanvas",
    "OrderedDither",
    "DitherDecision",
    "DitherPlanner",
    "DitherStrategy",
    "DiffusionCursor",
    "ErrorPropagationCursor",
    "ErrorSnapshot",
    "ResidualSnapshot",
    "DiffusionSnapshot",
    "ResidualState",
    "ErrorState",
    "PaintHistory",
    "SnapshotHistory",
    "UndoHistory",
    "History",
    "UndoManager",
    "HistoryManager",
    "HistoryEntry",
    "IndexMappingSnapshot",
    "ColorIndexMappingSnapshot",
    "PaintEngine",
    "boundary_stripe_pollution",
    "Palette",
    "PaletteEntry",
    "PaletteSnapshot",
    "PaletteView",
    "PaletteDisplay",
    "export_mapping",
    "build_export_mapping",
    "PALETTE_TABLES",
    "get_palette_table",
    "IndexPainting",
    "IndexPaintApp",
    "create_index_painting",
    "collect_index_evidence",
    "mapped_indices_equal",
    "read_png",
    "write_png",
    "reorder_palette",
    "load_project",
    "save_project",
]
