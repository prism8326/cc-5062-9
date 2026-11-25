import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from idxpaint.brush import Brush, Ramp
from idxpaint.engine import PaintEngine
from idxpaint.dither import OrderedDither, bayer_matrix
from tests._helpers import make_brush, make_canvas


def diagonal_points(w: int, h: int):
    return [(x + 0.5, x + 0.5, 0.2 + 0.6 * x / max(w - 1, 1))
            for x in range(min(w, h))]


class AnchorTests(unittest.TestCase):
    def test_bayer_matrices(self):
        m2 = bayer_matrix(1)
        self.assertEqual(m2, [[0, 2], [3, 1]])
        m4 = bayer_matrix(2)
        self.assertEqual(sorted(v for row in m4 for v in row), list(range(16)))
        m8 = bayer_matrix(3)
        self.assertEqual(sorted(v for row in m8 for v in row), list(range(64)))

    def test_threshold_is_coordinate_anchored(self):
        d = OrderedDither(3)
        self.assertEqual(d.threshold(5, 7), d.threshold(5 + 8, 7 + 16))
        self.assertNotEqual(d.threshold(0, 0), d.threshold(1, 0))

    def test_ordered_batching_does_not_move_phase(self):
        points = diagonal_points(20, 20)
        c1 = make_canvas(24, 24)
        PaintEngine(c1, make_brush()).paint_ordered(points)

        c2 = make_canvas(24, 24)
        engine = PaintEngine(c2, make_brush())
        # Non-overlapping batches sharing their boundary vertex: the engine
        # reuses the previous endpoint so cumulative arc length is preserved.
        for i in range(0, len(points) - 1, 4):
            engine.paint_ordered(points[i:i + 5])
        self.assertEqual(bytes(c1.raw_indices()), bytes(c2.raw_indices()))

    def test_pattern_independent_of_brush_radius(self):
        # Constant pressure: any index difference then comes purely from the
        # anchored dither threshold, never from geometry.
        points = [(x + 0.5, 10.0, 0.5) for x in range(20)]
        c_small = make_canvas(24, 24)
        b_small = make_brush(radius=1.0)
        PaintEngine(c_small, b_small).paint_ordered(points)
        c_big = make_canvas(24, 24)
        b_big = make_brush(radius=4.0)
        PaintEngine(c_big, b_big).paint_ordered(points)
        targets_big = PaintEngine(c_big, b_big).build_targets(points)
        full = {xy for xy, (_, cov, cx, cy) in targets_big.items()
                if b_big.is_fully_covered(xy[0], xy[1], cx, cy)}
        for x, y in full:
            if c_small.get_index(x, y) != 0:
                self.assertEqual(c_small.get_index(x, y), c_big.get_index(x, y),
                                 f"phase drifted at {x},{y}")

    def test_diffusion_tiled_matches_oneshot(self):
        points = diagonal_points(28, 28)
        c_one = make_canvas(32, 32)
        PaintEngine(c_one, make_brush()).paint_error_diffusion(points)

        for band_height in (1, 3, 5, 32):
            c_tile = make_canvas(32, 32)
            PaintEngine(c_tile, make_brush()).paint_error_diffusion_tiled(
                points, 32, band_height)
            self.assertEqual(bytes(c_one.raw_indices()), bytes(c_tile.raw_indices()),
                             f"band height {band_height} changed the result")

    def test_phase_survives_unrelated_prior_work(self):
        # Display zoom never repaints; and any preceding stroke (or leftover
        # diffusion state) must not shift the anchored ordered pattern.
        points = [(x + 0.5, 10.0, 0.5) for x in range(16)]
        c1 = make_canvas(24, 24)
        PaintEngine(c1, make_brush(radius=1.5)).paint_ordered(points)

        c2 = make_canvas(24, 24)
        busy = PaintEngine(c2, make_brush(radius=2.0))
        # An unrelated stroke elsewhere, then a fresh engine for the real one.
        busy.paint_ordered([(20 + 0.1 * i, 20 + 0.1 * i, 0.9) for i in range(20)])
        PaintEngine(c2, make_brush(radius=1.5)).paint_ordered(points)

        for x in range(16):
            self.assertEqual(c1.get_index(x, 10), c2.get_index(x, 10))

        # A second canvas painted from a clean engine gives the same indices.
        c3 = make_canvas(24, 24)
        PaintEngine(c3, make_brush(radius=1.5)).paint_ordered(points)
        self.assertEqual([c3.get_index(x, 10) for x in range(16)],
                         [c1.get_index(x, 10) for x in range(16)])


if __name__ == "__main__":
    unittest.main()
