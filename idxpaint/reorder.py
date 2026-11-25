"""Palette reordering with explicit identity semantics.

Two modes are offered and they are deliberately different:

* ``keep_appearance`` -- pixels are remapped so every stored index still
  resolves to the same RGBA after the palette moves.  The image looks
  identical; index *numbers* change.
* ``keep_identity`` -- stored indices are untouched, so a stroke that used
  index 5 still refers to entry 5 even though its colour may have moved.
  The image may visibly change, but no handwriting is silently rewritten.

Duplicate-RGB entries never merge: entries move as whole objects, carrying
alpha, name and lock state with them.
"""

from __future__ import annotations

from .canvas import IndexedCanvas


def reorder_palette(canvas: IndexedCanvas, permutation: list[int],
                    mode: str) -> dict[int, int]:
    """Apply *permutation* (old index -> position list) to the canvas palette.

    Returns the old-to-new index mapping actually applied to pixels.
    """
    palette = canvas.palette
    new_palette = palette.reorder(permutation)
    old_to_new = {old: new for new, old in enumerate(permutation)}

    if mode == "keep_appearance":
        canvas.replace_palette(new_palette, old_to_new)
        return old_to_new
    if mode == "keep_identity":
        canvas.replace_palette(new_palette, None)
        return {}
    raise ValueError("mode must be 'keep_appearance' or 'keep_identity'")


def appearance_after_reorder(canvas: IndexedCanvas, permutation: list[int]
                             ) -> list[tuple[int, int, int, int]]:
    """What each current pixel position would display after keep_appearance."""
    old_to_new = {old: new for new, old in enumerate(permutation)}
    new_palette = canvas.palette.reorder(permutation)
    out = []
    for i in range(canvas.width * canvas.height):
        old_index = canvas.raw_indices()[i]
        out.append(new_palette[old_to_new[old_index]].rgba)
    return out
