"""Indexed pixel canvas.

The canvas stores palette *indices* only -- a flat bytearray of values in
``[0, len(palette))``.  No RGB buffer ever exists, so painting cannot secretly
quantize a full-colour image: a brush must decide a concrete palette index for
every pixel it touches.
"""

from __future__ import annotations

from .palette import Palette


class IndexedCanvas:
    def __init__(self, width: int, height: int, palette: Palette,
                 transparent_index: int = 0, fill_index: int | None = None):
        if width <= 0 or height <= 0:
            raise ValueError("canvas dimensions must be positive")
        if not 0 <= transparent_index < len(palette):
            raise ValueError("transparent_index outside palette")
        self.width = width
        self.height = height
        self.palette = palette
        self.transparent_index = transparent_index
        fill = transparent_index if fill_index is None else fill_index
        if not 0 <= fill < len(palette):
            raise ValueError("fill_index outside palette")
        self._pixels = bytearray([fill]) * (width * height)
        # Entries that painting may never overwrite (palette-lock).
        self.locked_indices: set[int] = set()
        # Optional per-pixel protection mask; coordinate -> True means locked.
        self.pixel_locks: set[tuple[int, int]] = set()

    # -- storage -----------------------------------------------------------
    def get_index(self, x: int, y: int) -> int:
        return self._pixels[y * self.width + x]

    def set_index(self, x: int, y: int, index: int) -> None:
        self._pixels[y * self.width + x] = index

    def raw_indices(self) -> bytearray:
        return self._pixels

    def indices_copy(self) -> bytearray:
        return bytearray(self._pixels)

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def is_locked(self, x: int, y: int) -> bool:
        return (self.get_index(x, y) in self.locked_indices
                or (x, y) in self.pixel_locks)

    # -- semantics ---------------------------------------------------------
    def distinct_indices(self) -> set[int]:
        return set(self._pixels)

    def remap(self, mapping: dict[int, int]) -> None:
        """Rewrite stored indices through *mapping* (palette reorder support)."""
        out = bytearray(len(self._pixels))
        for i, v in enumerate(self._pixels):
            out[i] = mapping.get(v, v)
        self._pixels = out
        self.transparent_index = mapping.get(self.transparent_index,
                                             self.transparent_index)
        self.locked_indices = {mapping.get(v, v) for v in self.locked_indices}

    def replace_palette(self, palette: Palette, index_mapping: dict[int, int] | None = None) -> None:
        """Attach a reordered/edited palette, optionally remapping pixels."""
        if index_mapping is not None:
            self.remap(index_mapping)
        self.palette = palette
