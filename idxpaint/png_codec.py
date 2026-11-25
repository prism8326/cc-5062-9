"""Minimal PNG reader/writer for indexed (color-type-3) images.

Only the subset needed by the painting kernel is implemented, on top of the
standard library's ``zlib`` and ``struct``.  The round trip preserves palette
*indices* byte for byte, including the distinction between a transparent entry
and a normal entry that happens to share an RGB value.
"""

from __future__ import annotations

import struct
import zlib

from .canvas import IndexedCanvas
from .palette import Palette, PaletteEntry

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _chunk(tag: bytes, data: bytes) -> bytes:
    return (struct.pack(">I", len(data)) + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))


def write_png(path: str, canvas: IndexedCanvas) -> None:
    palette = canvas.palette
    if len(palette) == 0:
        raise ValueError("cannot encode a canvas with an empty palette")
    if len(palette) > 256:
        raise ValueError("PNG indexed images allow at most 256 palette entries")

    plte = b"".join(struct.pack("3B", *e.rgb) for e in palette)
    # tRNS must cover entries up to the last non-opaque one.
    trns_end = 0
    for i, e in enumerate(palette):
        if e.a != 255:
            trns_end = i + 1
    trns = bytes(palette[i].a for i in range(trns_end))

    bit_depth = 8 if len(palette) > 16 else (4 if len(palette) > 4 else
                                             (2 if len(palette) > 2 else 1))
    ihdr = struct.pack(">IIBBBBB", canvas.width, canvas.height,
                       bit_depth, 3, 0, 0, 0)

    raw = bytearray()
    stride = (canvas.width * bit_depth + 7) // 8
    for y in range(canvas.height):
        raw.append(0)  # filter type 0 (None)
        row = canvas.raw_indices()[y * canvas.width:(y + 1) * canvas.width]
        raw.extend(_pack_row(row, bit_depth, stride))

    data = zlib.compress(bytes(raw), 9)
    with open(path, "wb") as f:
        f.write(_PNG_SIGNATURE)
        f.write(_chunk(b"IHDR", ihdr))
        f.write(_chunk(b"PLTE", plte))
        if trns:
            f.write(_chunk(b"tRNS", trns))
        f.write(_chunk(b"IDAT", data))
        f.write(_chunk(b"IEND", b""))


def _pack_row(row: bytearray, bit_depth: int, stride: int) -> bytes:
    if bit_depth == 8:
        return bytes(row)
    out = bytearray(stride)
    mask = (1 << bit_depth) - 1
    ppb = 8 // bit_depth
    for i, v in enumerate(row):
        if bit_depth == 1:
            if v:
                out[i // ppb] |= 1 << (7 - (i % ppb))
        else:
            shift = 8 - bit_depth * (i % ppb + 1)
            out[i // ppb] |= (v & mask) << shift
    return bytes(out)


def read_png(path: str) -> IndexedCanvas:
    with open(path, "rb") as f:
        blob = f.read()
    if not blob.startswith(_PNG_SIGNATURE):
        raise ValueError("not a PNG file")
    pos = len(_PNG_SIGNATURE)
    chunks: dict[bytes, bytes] = {}
    while pos < len(blob):
        (length,) = struct.unpack(">I", blob[pos:pos + 4])
        tag = blob[pos + 4:pos + 8]
        data = blob[pos + 8:pos + 8 + length]
        chunks.setdefault(tag, b"")
        if tag == b"IDAT":
            chunks[tag] += data
        else:
            chunks[tag] = data
        pos += 12 + length

    width, height, bit_depth, color_type, _, _, _ = struct.unpack(
        ">IIBBBBB", chunks[b"IHDR"])
    if color_type != 3:
        raise ValueError(f"only indexed PNGs are supported, got color type {color_type}")
    if bit_depth not in (1, 2, 4, 8):
        raise ValueError(f"unsupported bit depth {bit_depth}")

    plte = chunks[b"PLTE"]
    entries = [PaletteEntry(plte[i], plte[i + 1], plte[i + 2])
               for i in range(0, len(plte), 3)]
    trns = chunks.get(b"tRNS", b"")
    for i, a in enumerate(trns):
        old = entries[i]
        entries[i] = PaletteEntry(old.r, old.g, old.b, a)
    palette = Palette(entries)

    raw = zlib.decompress(chunks[b"IDAT"])
    stride = (width * bit_depth + 7) // 8
    pixels = bytearray(width * height)
    ppb = 8 // bit_depth
    mask = (1 << bit_depth) - 1
    row_out = 0
    for y in range(height):
        filter_type = raw[y * (stride + 1)]
        if filter_type != 0:
            raise ValueError(f"filter type {filter_type} not supported by this reader")
        row = raw[y * (stride + 1) + 1:y * (stride + 1) + 1 + stride]
        for x in range(width):
            if bit_depth == 8:
                v = row[x]
            else:
                byte = row[x // ppb]
                shift = 8 - bit_depth * (x % ppb + 1)
                v = (byte >> shift) & mask
            pixels[row_out] = v
            row_out += 1

    # First fully transparent entry is treated as the transparent index.
    transparent_index = 0
    for i, e in enumerate(palette):
        if e.a == 0:
            transparent_index = i
            break
    canvas = IndexedCanvas(width, height, palette, transparent_index)
    canvas.raw_indices()[:] = pixels
    return canvas
