"""Execution evidence derived directly from live index canvas state."""

from __future__ import annotations

import base64

from .palette import export_mapping


def collect_index_evidence(canvas, *, include_base64: bool = True,
                           mapping: dict[int, int] | None = None) -> dict:
    """Collect actual index values plus the index -> RGBA export mapping.

    When *mapping* is supplied it is interpreted as the old-index -> new-index
    reorder mapping and included for equivalence checks.  Nothing here reads a
    UI RGB cache.
    """
    width, height = canvas.width, canvas.height
    raw = bytes(canvas.raw_indices())
    row_hex = []
    for y in range(height):
        row = raw[y * width:(y + 1) * width]
        row_hex.append(" ".join(f"{value:x}" for value in row))

    evidence = {
        "width": width,
        "height": height,
        "transparent_index": canvas.transparent_index,
        "distinct_indices": sorted(canvas.distinct_indices()),
        "index_rows_hex": row_hex,
        "export_mapping": {
            str(index): list(rgba)
            for index, rgba in export_mapping(canvas).items()
        },
        "locked_indices": sorted(getattr(canvas, "locked_indices", set())),
        "revision": getattr(canvas, "revision", None),
    }
    if include_base64:
        evidence["indices_base64"] = base64.b64encode(raw).decode("ascii")
    if mapping is not None:
        evidence["reorder_mapping"] = {str(k): v for k, v in mapping.items()}
    return evidence


def mapped_indices_equal(before: bytes | bytearray, after: bytes | bytearray,
                         old_to_new: dict[int, int] | None = None) -> bool:
    """Compare index buffers, applying an old->new export/reorder mapping."""
    if len(before) != len(after):
        return False
    if old_to_new is None:
        return bytes(before) == bytes(after)
    return all(old_to_new.get(old, old) == new for old, new in zip(before, after))
