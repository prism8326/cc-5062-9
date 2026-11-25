"""Palette-free index matrix and immutable index snapshots.

This is the narrow canvas interface used by painting, history and export
checks.  It stores integer indices only; interpreting those integers as
colours is the palette layer's job.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IndexSnapshot:
    """Restorable index-image state.

    ``pixels`` is stored as bytes so a snapshot can never be mutated through
    a returned bytearray.
    """

    width: int
    height: int
    transparent_index: int
    pixels: bytes
    locked_indices: frozenset[int] = frozenset()
    pixel_locks: frozenset[tuple[int, int]] = frozenset()
    revision: int = 0

    def restored(self, canvas: "IndexCanvas") -> "IndexCanvas":
        canvas.restore_indices(self)
        return canvas


class IndexCanvas:
    """A width x height matrix of palette indices.

    The optional ``color_count`` enables range validation.  It is intentionally
    optional because this class does not own a palette.
    """

    def __init__(
        self,
        width: int,
        height: int,
        transparent_index: int = 0,
        fill_index: int | None = None,
        color_count: int | None = None,
    ):
        if width <= 0 or height <= 0:
            raise ValueError("canvas dimensions must be positive")
        if color_count is not None and color_count <= 0:
            raise ValueError("color_count must be positive when provided")
        if transparent_index < 0:
            raise ValueError("transparent_index must be non-negative")
        if color_count is not None and not 0 <= transparent_index < color_count:
            raise ValueError("transparent_index outside palette")

        fill = transparent_index if fill_index is None else fill_index
        if fill < 0:
            raise ValueError("fill_index must be non-negative")
        if color_count is not None and not 0 <= fill < color_count:
            raise ValueError("fill_index outside palette")

        self.width = width
        self.height = height
        self.transparent_index = transparent_index
        self.color_count = color_count
        self._pixels = bytearray([fill]) * (width * height)
        self.locked_indices: set[int] = set()
        self.pixel_locks: set[tuple[int, int]] = set()
        self.revision = 0

    @property
    def version(self) -> int:
        return self.revision

    def get_index(self, x: int, y: int) -> int:
        return self._pixels[y * self.width + x]

    def set_index(self, x: int, y: int, index: int) -> None:
        if not self.in_bounds(x, y):
            raise IndexError(f"pixel coordinate ({x}, {y}) is outside canvas")
        if index < 0 or (self.color_count is not None and index >= self.color_count):
            raise ValueError(f"index {index} is outside the available colour table")
        offset = y * self.width + x
        if self._pixels[offset] != index:
            self._pixels[offset] = index
            self.revision += 1
        else:
            self._pixels[offset] = index

    def raw_indices(self) -> bytearray:
        return self._pixels

    def indices_copy(self) -> bytearray:
        return bytearray(self._pixels)

    def index_bytes(self) -> bytes:
        return bytes(self._pixels)

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def is_locked(self, x: int, y: int) -> bool:
        return (self.get_index(x, y) in self.locked_indices
                or (x, y) in self.pixel_locks)

    def distinct_indices(self) -> set[int]:
        return set(self._pixels)

    def fill(self, index: int) -> None:
        if index < 0 or (self.color_count is not None and index >= self.color_count):
            raise ValueError(f"index {index} is outside the available colour table")
        self._pixels[:] = bytearray([index]) * (self.width * self.height)
        self.revision += 1

    def remap(self, mapping: dict[int, int]) -> None:
        """Rewrite stored indices and index-keyed edit state through mapping."""
        out = bytearray(len(self._pixels))
        for i, value in enumerate(self._pixels):
            new_value = mapping.get(value, value)
            if new_value < 0 or (
                self.color_count is not None and new_value >= self.color_count
            ):
                raise ValueError(f"mapping produces out-of-range index {new_value}")
            out[i] = new_value
        self._pixels = out
        self.transparent_index = mapping.get(
            self.transparent_index, self.transparent_index
        )
        self.locked_indices = {
            mapping.get(value, value) for value in self.locked_indices
        }
        self.revision += 1

    # -- snapshots and diffs ------------------------------------------------
    def snapshot(self) -> IndexSnapshot:
        return IndexSnapshot(
            width=self.width,
            height=self.height,
            transparent_index=self.transparent_index,
            pixels=bytes(self._pixels),
            locked_indices=frozenset(self.locked_indices),
            pixel_locks=frozenset(self.pixel_locks),
            revision=self.revision,
        )

    def indices_snapshot(self) -> IndexSnapshot:
        return self.snapshot()

    def restore_indices(self, snapshot: IndexSnapshot) -> None:
        if (snapshot.width, snapshot.height) != (self.width, self.height):
            raise ValueError("snapshot dimensions do not match canvas")
        if len(snapshot.pixels) != self.width * self.height:
            raise ValueError("snapshot pixel data has the wrong length")
        if self.color_count is not None:
            out_of_range = [
                value for value in snapshot.pixels if value >= self.color_count
            ]
            if out_of_range:
                raise ValueError("snapshot contains indices outside the colour table")
            if not 0 <= snapshot.transparent_index < self.color_count:
                raise ValueError("snapshot transparent_index outside colour table")
        self._pixels = bytearray(snapshot.pixels)
        self.transparent_index = snapshot.transparent_index
        self.locked_indices = set(snapshot.locked_indices)
        self.pixel_locks = set(snapshot.pixel_locks)
        self.revision = snapshot.revision + 1

    restore = restore_indices

    def changed_cells(self, other: "IndexCanvas | IndexSnapshot | bytes") -> list[tuple[int, int, int, int]]:
        """Return ``(x, y, old_index, new_index)`` differences versus other."""
        if isinstance(other, IndexSnapshot):
            if (other.width, other.height) != (self.width, self.height):
                raise ValueError("comparison dimensions do not match canvas")
            old = other.pixels
        elif isinstance(other, (bytes, bytearray)):
            old = bytes(other)
            if len(old) != len(self._pixels):
                raise ValueError("comparison buffer has the wrong length")
        else:
            if (other.width, other.height) != (self.width, self.height):
                raise ValueError("comparison dimensions do not match canvas")
            old = bytes(other.raw_indices())

        changes = []
        for offset, new_value in enumerate(self._pixels):
            old_value = old[offset]
            if old_value != new_value:
                changes.append((
                    offset % self.width,
                    offset // self.width,
                    old_value,
                    new_value,
                ))
        return changes

    def diff_indices(self, before: "IndexCanvas | IndexSnapshot | bytes") -> dict:
        changes = self.changed_cells(before)
        return {
            "changed_count": len(changes),
            "changes": changes,
            "before_indices": sorted({old for _, _, old, _ in changes}),
            "after_indices": sorted({new for _, _, _, new in changes}),
            "transparent_index": self.transparent_index,
        }


IndexCanvasSnapshot = IndexSnapshot
CanvasSnapshot = IndexSnapshot
