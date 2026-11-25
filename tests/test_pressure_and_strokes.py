import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from idxpaint.brush import Ramp
from idxpaint.engine import PaintEngine
from tests._helpers import make_brush, make_canvas


class PressureGradientTests(unittest.TestCase):
    def test_finite_ramp_uses_only_ramp_indices(self):
        canvas = make_canvas(40, 10)
        ramp = Ramp((1, 2, 3, 4))
        brush = make_brush(ramp=ramp, radius=1.0, spacing=1.0)
        points = [(x + 0.5, 5.0, x / 39.0) for x in range(40)]
        used = PaintEngine(canvas, brush).paint_ordered(points)
        self.assertTrue(used.issubset(set(ramp.indices) | {canvas.transparent_index}))
        # A 4-step gradient over 40 pressure levels must actually exercise
        # every step rather than collapsing to the endpoints.
        self.assertEqual(used & set(ramp.indices), set(ramp.indices))

    def test_pressure_endpoints_hit_end_steps(self):
        canvas = make_canvas(12, 4)
        ramp = Ramp((1, 2, 3, 4))
        brush = make_brush(ramp=ramp, radius=0.6)
        PaintEngine(canvas, brush).paint_ordered([(1.5, 1.5, 0.0)])
        PaintEngine(canvas, brush).paint_ordered([(10.5, 1.5, 1.0)])
        self.assertEqual(canvas.get_index(1, 1), ramp.indices[0])
        self.assertEqual(canvas.get_index(10, 1), ramp.indices[-1])

    def test_single_step_ramp_is_flat(self):
        canvas = make_canvas(16, 8)
        brush = make_brush(ramp=Ramp((7,)), radius=2.0)
        used = PaintEngine(canvas, brush).paint_ordered(
            [(x + 0.5, 4.0, x / 15.0) for x in range(16)])
        self.assertEqual(used - {canvas.transparent_index}, {7})

    def test_cross_tile_diagonal_is_continuous(self):
        w = h = 33
        points = [(i + 0.5, i + 0.5, i / 32.0) for i in range(33)]

        # Ordered mode with a hard brush: the stroke must be gap-free across
        # band seams and use only the finite ramp's indices.
        canvas = make_canvas(w, h)
        PaintEngine(canvas, make_brush(radius=1.5, soft_edge=0.0)).paint_ordered(points)
        diagonal = [canvas.get_index(i, i) for i in range(33)]
        self.assertNotIn(canvas.transparent_index, diagonal)
        for boundary in (8, 16, 24):
            self.assertNotEqual(canvas.get_index(boundary - 1, boundary - 1),
                                canvas.transparent_index)
            self.assertNotEqual(canvas.get_index(boundary, boundary),
                                canvas.transparent_index)
        # Every pixel the stroke touched uses a ramp index, never background.
        touched = PaintEngine(canvas, make_brush(radius=1.5, soft_edge=0.0)
                              ).build_targets(points)
        self.assertTrue(all(canvas.get_index(x, y) in {1, 2, 3, 4}
                            for x, y in touched))

        # Diffusion mode: band-tiled processing equals one-shot processing and
        # every index used still belongs to the finite ramp.
        c_band = make_canvas(w, h)
        PaintEngine(c_band, make_brush(radius=1.5, soft_edge=0.0)).paint_error_diffusion_tiled(
            points, w, 8)
        c_one = make_canvas(w, h)
        PaintEngine(c_one, make_brush(radius=1.5, soft_edge=0.0)).paint_error_diffusion(points)
        self.assertEqual(bytes(c_band.raw_indices()), bytes(c_one.raw_indices()))
        self.assertTrue(c_band.distinct_indices().issubset({0, 1, 2, 3, 4}))

    def test_stroke_determinism(self):
        points = [(i * 0.7 + 0.3, 5 + (i % 3) * 0.4, i / 20.0) for i in range(21)]
        c1, c2 = make_canvas(24, 12), make_canvas(24, 12)
        PaintEngine(c1, make_brush()).paint_ordered(points)
        PaintEngine(c2, make_brush()).paint_ordered(points)
        self.assertEqual(bytes(c1.raw_indices()), bytes(c2.raw_indices()))


if __name__ == "__main__":
    unittest.main()
