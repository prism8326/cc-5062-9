"""Application facade for index painting callers.

This wires the index canvas, palette display boundary, dither/error cursor and
history together.  Existing low-level entry points (``IndexedCanvas``,
``PaintEngine`` and ``reorder_palette``) remain available as compatibility
adapters.
"""

from __future__ import annotations

from .brush import Brush, Ramp
from .canvas import IndexedCanvas
from .engine import PaintEngine
from .evidence import collect_index_evidence
from .history import PaintHistory
from .palette import PaletteView
from .palettes import get_palette_table
from .reorder import reorder_palette
from .storage import save_project


class IndexPainting:
    def __init__(
        self,
        width: int = 48,
        height: int = 32,
        palette= "demo",
        transparent_index: int = 0,
        brush: Brush | None = None,
    ):
        palette_obj = get_palette_table(palette) if isinstance(palette, str) else palette
        self.canvas = IndexedCanvas(
            width, height, palette_obj, transparent_index=transparent_index
        )
        self.palette_view = PaletteView(palette_obj)
        self.history = PaintHistory()
        if brush is None:
            last_ramp = min(4, len(palette_obj) - 1)
            ramp = Ramp(tuple(range(1, last_ramp + 1)))
            brush = Brush(ramp=ramp, radius=2.0, spacing=1.0)
        self.brush = brush
        self.engine = PaintEngine(self.canvas, brush)

    def select_palette_table(self, table: str, *, remap: dict[int, int] | None = None) -> dict[int, int] | None:
        """Switch the displayed colour table while preserving stored indices."""
        palette = get_palette_table(table)
        self.history.checkpoint(
            "select-palette-table", self.canvas, self.engine.diffusion_cursor
        )
        self.canvas.replace_palette(palette, remap)
        self.palette_view = PaletteView(palette)
        return remap

    def reorder_palette(self, permutation: list[int], mode: str) -> dict[int, int]:
        self.history.checkpoint(
            "reorder-palette", self.canvas, self.engine.diffusion_cursor
        )
        mapping = reorder_palette(self.canvas, permutation, mode)
        self.palette_view = PaletteView(self.canvas.palette)
        return mapping

    def paint_gradient(
        self,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        *,
        mode: str = "ordered",
        samples: int | None = None,
        region: tuple[int, int, int, int] | None = None,
        record_undo: bool = True,
    ) -> set[int]:
        import math
        length = max(1.0, math.hypot(x1 - x0, y1 - y0))
        count = samples if samples is not None else max(2, int(length / max(self.brush.spacing, 0.5)) + 1)
        points = []
        for i in range(count):
            t = i / max(count - 1, 1)
            points.append((
                x0 + (x1 - x0) * t,
                y0 + (y1 - y0) * t,
                t,
            ))
        if record_undo:
            self.history.checkpoint(
                "gradient", self.canvas, self.engine.diffusion_cursor
            )
        if mode == "ordered":
            return self.engine.paint_ordered(points)
        if mode == "diffusion":
            return self.engine.paint_error_diffusion(points, region=region)
        raise ValueError("mode must be 'ordered' or 'diffusion'")

    def undo(self):
        entry = self.history.undo(self.canvas, self.engine.diffusion_cursor)
        self.palette_view = PaletteView(self.canvas.palette)
        return entry

    def save_project(self, path_no_ext: str) -> tuple[str, str]:
        return save_project(self.canvas, path_no_ext)

    def export_mapping(self) -> dict[int, tuple[int, int, int, int]]:
        return self.canvas.export_palette_mapping()

    def evidence(self) -> dict:
        return collect_index_evidence(self.canvas)


IndexPaintApp = IndexPainting
create_index_painting = IndexPainting
