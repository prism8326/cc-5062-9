import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from idxpaint.brush import AlphaPolicy, Ramp
from idxpaint.engine import PaintEngine
from tests._helpers import make_brush, make_canvas


class AlphaPolicyTests(unittest.TestCase):
    def test_keep_transparent_never_replaces_transparent_index(self):
        canvas = make_canvas(20, 8)
        brush = make_brush(ramp=Ramp((7,)), radius=2.0, soft_edge=1.0,
                           alpha_policy=AlphaPolicy.KEEP_TRANSPARENT)
        PaintEngine(canvas, brush).paint_ordered(
            [(x + 0.5, 4.0, 1.0) for x in range(4, 16)])
        # Fully covered cores become ink; fringe cells with cov < 1 keep 0.
        used = canvas.distinct_indices()
        self.assertIn(7, used)
        fringe_kept = any(canvas.get_index(x, y) == canvas.transparent_index
                          for x in range(4, 16) for y in (2, 3, 5, 6))
        self.assertTrue(fringe_kept)

    def test_dither_mixes_transparent_and_ink(self):
        canvas = make_canvas(20, 8)
        brush = make_brush(ramp=Ramp((7,)), radius=2.0, soft_edge=1.0,
                           alpha_policy=AlphaPolicy.DITHER)
        PaintEngine(canvas, brush).paint_ordered(
            [(x + 0.5, 4.0, 1.0) for x in range(4, 16)])
        self.assertIn(7, canvas.distinct_indices())
        self.assertIn(canvas.transparent_index, canvas.distinct_indices())

    def test_overwrite_ignores_coverage(self):
        canvas = make_canvas(20, 8)
        brush = make_brush(ramp=Ramp((7,)), radius=2.0, soft_edge=1.0,
                           alpha_policy=AlphaPolicy.OVERWRITE)
        PaintEngine(canvas, brush).paint_ordered(
            [(x + 0.5, 4.0, 1.0) for x in range(4, 16)])
        # Every touched stamp cell is ink; no transparent cells remain inside.
        targets = PaintEngine(canvas, brush).build_targets(
            [(x + 0.5, 4.0, 1.0) for x in range(4, 16)])
        self.assertTrue(all(canvas.get_index(x, y) == 7 for x, y in targets))

    def test_transparent_index_distinct_from_visually_equal_entry(self):
        # Even if an entry had the same RGB as the background, the transparent
        # index stays its own index under every policy.
        canvas = make_canvas(8, 8)
        canvas.palette.set_color(0, (0, 0, 0, 0))
        canvas.set_index(3, 3, 1)
        brush = make_brush(ramp=Ramp((1,)), radius=1.0,
                           alpha_policy=AlphaPolicy.KEEP_TRANSPARENT)
        PaintEngine(canvas, brush).paint_ordered([(0.5, 0.5, 1.0)])
        self.assertEqual(canvas.get_index(0, 0), 1)
        self.assertEqual(canvas.get_index(7, 7), canvas.transparent_index)
        self.assertNotEqual(canvas.transparent_index, 1)


if __name__ == "__main__":
    unittest.main()
