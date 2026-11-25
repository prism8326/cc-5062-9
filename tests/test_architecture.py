"""Architectural guarantees: painting is index editing, not quantized RGB."""

import inspect
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from idxpaint import canvas as canvas_mod
from idxpaint import engine as engine_mod
from idxpaint.engine import PaintEngine
from tests._helpers import make_brush, make_canvas


class NoFullColorQuantizeTests(unittest.TestCase):
    def test_canvas_storage_is_index_only(self):
        canvas = make_canvas(8, 8)
        # The mutable pixel store is a bytearray of palette indices.
        self.assertIsInstance(canvas.raw_indices(), bytearray)
        for v in canvas.raw_indices():
            self.assertIsInstance(v, int)
            self.assertLess(v, len(canvas.palette))
        # No RGB-shaped framebuffer attribute exists on the canvas.
        for name in vars(canvas):
            self.assertNotIn(name.lower(), ("rgb", "rgba", "image", "bitmap",
                                            "pixels_rgb", "color_buffer"))

    def test_engine_has_no_quantization_routine(self):
        source = inspect.getsource(engine_mod)
        for needle in ("quantize", "nearest_color", "to_rgb", "from_rgb",
                       "rgb_to_index", "snap_to_palette"):
            self.assertNotIn(needle, source.lower())
        # Brushes hand indices straight to the canvas; the write path only
        # ever passes integers that already name palette entries.
        write_src = inspect.getsource(canvas_mod.IndexedCanvas.set_index)
        self.assertNotIn("rgb", write_src.lower())

    def test_painting_never_exceeds_palette_range(self):
        canvas = make_canvas(20, 20)
        brush = make_brush(radius=4.0)
        PaintEngine(canvas, brush).paint_ordered(
            [(10 + 0.3 * i, 10 + 0.2 * i, i / 30.0) for i in range(31)])
        n = len(canvas.palette)
        self.assertTrue(all(0 <= v < n for v in canvas.raw_indices()))


if __name__ == "__main__":
    unittest.main()
