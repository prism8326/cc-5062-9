"""Project storage: indexed PNG plus a JSON sidecar carrying edit semantics.

The PNG keeps the portable image (palette entries and indices).  The sidecar
records everything a flat image cannot express: which entry is the
transparent index, palette/pixel locks, and a base64 copy of the raw indices
so a browser viewer can display index-level information without decoding PNG.
"""

from __future__ import annotations

import base64
import json
import os

from .canvas import IndexedCanvas
from .png_codec import read_png, write_png

SIDECAR_VERSION = 1


def save_project(canvas: IndexedCanvas, path_no_ext: str) -> tuple[str, str]:
    png_path = path_no_ext + ".png"
    json_path = path_no_ext + ".idx.json"
    write_png(png_path, canvas)
    payload = {
        "version": SIDECAR_VERSION,
        "width": canvas.width,
        "height": canvas.height,
        "transparent_index": canvas.transparent_index,
        "locked_indices": sorted(canvas.locked_indices),
        "pixel_locks": sorted(canvas.pixel_locks),
        "palette": [
            {"r": e.r, "g": e.g, "b": e.b, "a": e.a, "name": e.name}
            for e in canvas.palette
        ],
        "indices_base64": base64.b64encode(bytes(canvas.raw_indices())).decode("ascii"),
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return png_path, json_path


def load_project(path_no_ext: str) -> IndexedCanvas:
    json_path = path_no_ext + ".idx.json"
    png_path = path_no_ext + ".png"
    if os.path.exists(json_path):
        with open(json_path, encoding="utf-8") as f:
            payload = json.load(f)
        canvas = read_png(png_path)
        canvas.transparent_index = payload["transparent_index"]
        canvas.locked_indices = set(payload.get("locked_indices", []))
        canvas.pixel_locks = {tuple(p) for p in payload.get("pixel_locks", [])}
        if "indices_base64" in payload:
            stored = base64.b64decode(payload["indices_base64"])
            if bytes(canvas.raw_indices()) != stored:
                raise ValueError("PNG indices disagree with sidecar indices")
        return canvas
    return read_png(png_path)
