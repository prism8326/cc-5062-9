"""Indexed pixel canvas with its palette mapping attached.

The pixel matrix itself is implemented by :class:`idxpaint.index_canvas.IndexCanvas`.
This subclass keeps the historical ``IndexedCanvas(width, height, palette)``
entry point and attaches the palette responsible for displaying/exporting
indices.  No RGB framebuffer is ever stored here.
"""

from __future__ import annotations

from .index_canvas import IndexCanvas as _IndexCanvas
from .palette import Palette


class IndexedCanvas(_IndexCanvas):
    def __init__(self, width: int, height: int, palette: Palette,
                 transparent_index: int = 0, fill_index: int | None = None):
        if not 0 <= transparent_index < len(palette):
            raise ValueError("transparent_index outside palette")
        fill = transparent_index if fill_index is None else fill_index
        if not 0 <= fill < len(palette):
            raise ValueError("fill_index outside palette")
        super().__init__(
            width,
            height,
            transparent_index=transparent_index,
            fill_index=fill,
            color_count=len(palette),
        )
        self.palette = palette

    def remap(self, mapping: dict[int, int]) -> None:
        for new_index in mapping.values():
            if not 0 <= new_index < len(self.palette):
                raise ValueError("palette mapping points outside palette")
        super().remap(mapping)

    def replace_palette(self, palette: Palette, index_mapping: dict[int, int] | None = None) -> None:
        """Attach a reordered/edited palette, optionally remapping pixels."""
        old_color_count = self.color_count
        self.color_count = len(palette)
        try:
            if index_mapping is not None:
                self.remap(index_mapping)
            else:
                out_of_range = [v for v in self._pixels if v >= len(palette)]
                if out_of_range:
                    raise ValueError("existing indices are outside replacement palette")
                if self.transparent_index >= len(palette):
                    raise ValueError("transparent_index outside replacement palette")
        except Exception:
            self.color_count = old_color_count
            raise
        self.palette = palette

    def export_palette_mapping(self) -> dict[int, tuple[int, int, int, int]]:
        return {i: entry.rgba for i, entry in enumerate(self.palette)}
