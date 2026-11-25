import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from idxpaint.png_codec import read_png, write_png
from idxpaint.palette import Palette, PaletteEntry
from idxpaint.canvas import IndexedCanvas
from tests._helpers import tmp_png


class PngRoundTripTests(unittest.TestCase):
    def _round_trip(self, n_entries: int, w: int = 13, h: int = 7):
        entries = [PaletteEntry(i * 7 % 256, i * 13 % 256, i * 29 % 256,
                                0 if i == 0 else 255)
                   for i in range(n_entries)]
        palette = Palette(entries)
        canvas = IndexedCanvas(w, h, palette, transparent_index=0)
        for y in range(h):
            for x in range(w):
                canvas.set_index(x, y, (x * 3 + y * 5) % n_entries)
        path = tmp_png()
        write_png(path, canvas)
        reloaded = read_png(path)
        self.assertEqual(reloaded.width, w)
        self.assertEqual(reloaded.height, h)
        self.assertEqual(bytes(reloaded.raw_indices()), bytes(canvas.raw_indices()))
        self.assertEqual([e.rgba for e in reloaded.palette],
                         [e.rgba for e in palette])
        self.assertEqual(reloaded.transparent_index, 0)
        os.unlink(path)

    def test_bit_depths_1_2_4_8(self):
        for n in (2, 4, 16, 256):
            with self.subTest(entries=n):
                self._round_trip(n)

    def test_trns_partial_alpha(self):
        palette = Palette([
            PaletteEntry(0, 0, 0, 0),
            PaletteEntry(10, 10, 10, 128),
            PaletteEntry(20, 20, 20, 255),
        ])
        canvas = IndexedCanvas(4, 2, palette, transparent_index=0)
        for x in range(4):
            canvas.set_index(x, 0, x % 3)
        path = tmp_png()
        write_png(path, canvas)
        reloaded = read_png(path)
        self.assertEqual(reloaded.palette[0].a, 0)
        self.assertEqual(reloaded.palette[1].a, 128)
        self.assertEqual(reloaded.palette[2].a, 255)
        os.unlink(path)

    def test_duplicate_rgb_entries_remain_distinct(self):
        palette = Palette([
            PaletteEntry(0, 0, 0, 0),
            PaletteEntry(99, 99, 99, 255, "first"),
            PaletteEntry(99, 99, 99, 255, "second"),
        ])
        canvas = IndexedCanvas(3, 1, palette, transparent_index=0)
        canvas.set_index(0, 0, 1)
        canvas.set_index(1, 0, 2)
        path = tmp_png()
        write_png(path, canvas)
        reloaded = read_png(path)
        self.assertEqual(reloaded.get_index(0, 0), 1)
        self.assertEqual(reloaded.get_index(1, 0), 2)
        self.assertEqual(reloaded.palette[1].rgba, reloaded.palette[2].rgba)
        self.assertIsNot(reloaded.palette[1], reloaded.palette[2])
        os.unlink(path)

    def test_file_is_real_indexed_png(self):
        palette = Palette([PaletteEntry(0, 0, 0, 0), PaletteEntry(9, 9, 9)])
        canvas = IndexedCanvas(2, 2, palette)
        path = tmp_png()
        write_png(path, canvas)
        with open(path, "rb") as f:
            blob = f.read()
        self.assertTrue(blob.startswith(b"\x89PNG\r\n\x1a\n"))
        # IHDR layout after the tag: width(4) height(4) depth(1) type(1) ...
        ihdr_start = blob.index(b"IHDR") + 4
        bit_depth = blob[ihdr_start + 8]
        color_type = blob[ihdr_start + 9]
        self.assertEqual(bit_depth, 1)
        self.assertEqual(color_type, 3)
        self.assertIn(b"PLTE", blob)
        os.unlink(path)


if __name__ == "__main__":
    unittest.main()
