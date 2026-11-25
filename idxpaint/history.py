"""Undo history composed from independent index/error/palette snapshots.

The snapshots are separate because the states have different lifetimes:

* :class:`~idxpaint.index_canvas.IndexSnapshot` owns stored index values;
* :class:`~idxpaint.diffusion.ErrorSnapshot` owns pending diffusion residuals;
* :class:`PaletteSnapshot` owns the colour table/display mapping;
* :class:`IndexMappingSnapshot` records an old-index -> new-index remap.

A history entry composes them at an undo boundary.  After a palette reorder,
undo therefore restores the original indices together with the residuals that
were waiting for the next diffusion row.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .diffusion import DiffusionCursor, ErrorSnapshot
from .index_canvas import IndexCanvas, IndexSnapshot
from .palette import Palette, PaletteSnapshot


@dataclass(frozen=True)
class IndexMappingSnapshot:
    mapping: tuple[tuple[int, int], ...] = ()
    mode: str | None = None

    @classmethod
    def of(cls, mapping: dict[int, int], mode: str | None = None) -> "IndexMappingSnapshot":
        return cls(tuple(sorted(mapping.items())), mode)

    def as_dict(self) -> dict[int, int]:
        return dict(self.mapping)


ColorIndexMappingSnapshot = IndexMappingSnapshot


@dataclass
class HistoryEntry:
    label: str
    indices: IndexSnapshot
    errors: ErrorSnapshot | None = None
    palette: PaletteSnapshot | None = None
    mapping: IndexMappingSnapshot | None = None


class PaintHistory:
    def __init__(self):
        self._undo: list[HistoryEntry] = []
        self._redo: list[HistoryEntry] = []

    def __len__(self) -> int:
        return len(self._undo)

    def can_undo(self) -> bool:
        return bool(self._undo)

    def can_redo(self) -> bool:
        return bool(self._redo)

    def checkpoint(
        self,
        label: str,
        canvas: IndexCanvas,
        cursor: DiffusionCursor | None = None,
        palette: Palette | PaletteSnapshot | None = None,
        mapping: dict[int, int] | IndexMappingSnapshot | None = None,
    ) -> HistoryEntry:
        """Capture the state that a later undo should restore."""
        if palette is None and hasattr(canvas, "palette"):
            palette = canvas.palette
        if isinstance(palette, Palette):
            palette_snapshot = palette.snapshot()
        else:
            palette_snapshot = palette

        if mapping is None or isinstance(mapping, IndexMappingSnapshot):
            mapping_snapshot = mapping
        else:
            mapping_snapshot = IndexMappingSnapshot.of(mapping)

        entry = HistoryEntry(
            label=label,
            indices=canvas.snapshot(),
            errors=cursor.snapshot() if cursor is not None else None,
            palette=palette_snapshot,
            mapping=mapping_snapshot,
        )
        self._undo.append(entry)
        self._redo.clear()
        return entry

    # Wording-level aliases.
    commit = checkpoint
    capture = checkpoint

    def undo(
        self,
        canvas: IndexCanvas,
        cursor: DiffusionCursor | None = None,
    ) -> HistoryEntry:
        if not self._undo:
            raise IndexError("nothing to undo")
        entry = self._undo.pop()
        self._redo.append(HistoryEntry(
            label=entry.label,
            indices=canvas.snapshot(),
            errors=cursor.snapshot() if cursor is not None else None,
            palette=canvas.palette.snapshot() if hasattr(canvas, "palette") else None,
        ))
        canvas.restore_indices(entry.indices)
        if entry.palette is not None and hasattr(canvas, "palette"):
            canvas.palette = entry.palette.to_palette()
            if hasattr(canvas, "color_count"):
                canvas.color_count = len(entry.palette)
        if cursor is not None:
            if entry.errors is None:
                cursor.clear()
            else:
                cursor.restore(entry.errors)
        return entry

    def redo(
        self,
        canvas: IndexCanvas,
        cursor: DiffusionCursor | None = None,
    ) -> HistoryEntry:
        if not self._redo:
            raise IndexError("nothing to redo")
        entry = self._redo.pop()
        self._undo.append(HistoryEntry(
            label=entry.label,
            indices=canvas.snapshot(),
            errors=cursor.snapshot() if cursor is not None else None,
            palette=canvas.palette.snapshot() if hasattr(canvas, "palette") else None,
        ))
        canvas.restore_indices(entry.indices)
        if entry.palette is not None and hasattr(canvas, "palette"):
            canvas.palette = entry.palette.to_palette()
            if hasattr(canvas, "color_count"):
                canvas.color_count = len(entry.palette)
        if cursor is not None:
            if entry.errors is None:
                cursor.clear()
            else:
                cursor.restore(entry.errors)
        return entry


# Descriptive aliases.
SnapshotHistory = PaintHistory
UndoHistory = PaintHistory
History = PaintHistory
UndoManager = PaintHistory
HistoryManager = PaintHistory
