import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from idxpaint.brush import LockPolicy, Ramp
from idxpaint.engine import PaintEngine, boundary_stripe_pollution
from tests._helpers import make_brush, make_canvas


class LockConflictTests(unittest.TestCase):
    def _setup(self, policy: LockPolicy):
        canvas = make_canvas(24, 16)
        # Horizontal locked wall of accent index 5 across y=8.
        canvas.locked_indices.add(5)
        for x in range(canvas.width):
            canvas.set_index(x, 8, 5)
        brush = make_brush(radius=1.5, lock_policy=policy)
        engine = PaintEngine(canvas, brush)
        points = [(x + 0.5, 6.0 + 0.12 * x, 0.75) for x in range(24)]
        return canvas, engine, points

    def test_locked_pixels_are_never_overwritten(self):
        for policy in (LockPolicy.RESTART, LockPolicy.CARRY):
            canvas, engine, points = self._setup(policy)
            engine.paint_error_diffusion(points, region=(0, 4, 23, 11))
            wall = [canvas.get_index(x, 8) for x in range(24)]
            self.assertTrue(all(v == 5 for v in wall),
                            f"{policy} damaged the locked wall")

    def test_restart_drops_residual_carry_keeps_it(self):
        c_restart, e_restart, pts = self._setup(LockPolicy.RESTART)
        e_restart.paint_error_diffusion(pts, region=(0, 4, 23, 11))

        c_carry, e_carry, _ = self._setup(LockPolicy.CARRY)
        e_carry.paint_error_diffusion(pts, region=(0, 4, 23, 11))

        above_restart = [c_restart.get_index(x, 9) for x in range(24)]
        above_carry = [c_carry.get_index(x, 9) for x in range(24)]
        # With RESTART the residual is discarded at the wall; the row beyond
        # the wall only gets fresh diffusion from its own targets.  CARRY
        # must produce a measurably different distribution somewhere.
        self.assertNotEqual(above_restart, above_carry)
        # And neither policy may corrupt the wall itself.
        self.assertTrue(all(c_carry.get_index(x, 8) == 5 for x in range(24)))

    def test_pixel_lock_mask_is_respected(self):
        canvas = make_canvas(10, 10)
        canvas.pixel_locks.add((5, 5))
        canvas.set_index(5, 5, 7)
        PaintEngine(canvas, make_brush(radius=3.0)).paint_ordered(
            [(5.0, 5.0, 1.0)])
        self.assertEqual(canvas.get_index(5, 5), 7)

    def test_boundary_stripe_measures_pollution(self):
        clean = make_canvas(12, 12)
        dirty = make_canvas(12, 12)
        rect = (2, 2, 9, 9)
        # No paint at all -> zero pollution.
        self.assertEqual(boundary_stripe_pollution(clean, dirty, rect, "top"), 0)
        # A change placed inside the stripe is counted.
        dirty.set_index(2, 1, 3)
        dirty.set_index(9, 1, 4)
        dirty.set_index(5, 0, 2)  # outside a width-1 stripe
        self.assertEqual(boundary_stripe_pollution(clean, dirty, rect, "top", 1), 2)
        self.assertEqual(boundary_stripe_pollution(clean, dirty, rect, "top", 2), 3)

    def test_diffusion_confined_to_region_has_zero_external_pollution(self):
        canvas = make_canvas(20, 20)
        before = make_canvas(20, 20)
        before.raw_indices()[:] = canvas.raw_indices()
        brush = make_brush(radius=2.0)
        PaintEngine(canvas, brush).paint_error_diffusion(
            [(x + 0.5, 10.0, 0.6) for x in range(4, 16)],
            region=(3, 8, 16, 12))
        for side in ("top", "bottom", "left", "right"):
            self.assertEqual(
                boundary_stripe_pollution(before, canvas, (3, 8, 16, 12), side),
                0, f"residual leaked through {side}")


if __name__ == "__main__":
    unittest.main()
