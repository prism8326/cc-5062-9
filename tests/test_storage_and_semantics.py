import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from idxpaint.brush import LockPolicy, Ramp
from idxpaint.engine import PaintEngine
from idxpaint.storage import load_project, save_project
from tests._helpers import make_brush, make_canvas, tmp_project


class StorageRoundTripTests(unittest.TestCase):
    def test_project_round_trip_preserves_indices_and_semantics(self):
        canvas = make_canvas(24, 16)
        canvas.locked_indices.add(5)
        canvas.pixel_locks.add((2, 2))
        brush = make_brush(radius=2.0, lock_policy=LockPolicy.CARRY)
        PaintEngine(canvas, brush).paint_ordered(
            [(x + 0.5, 8.0, x / 23.0) for x in range(24)])
        expected = bytes(canvas.raw_indices())

        base = tmp_project()
        png_path, json_path = save_project(canvas, base)
        self.assertTrue(os.path.exists(png_path))
        self.assertTrue(os.path.exists(json_path))

        reloaded = load_project(base)
        self.assertEqual(bytes(reloaded.raw_indices()), expected)
        self.assertEqual(reloaded.transparent_index, canvas.transparent_index)
        self.assertEqual(reloaded.locked_indices, {5})
        self.assertEqual(reloaded.pixel_locks, {(2, 2)})
        self.assertEqual([e.rgba for e in reloaded.palette],
                         [e.rgba for e in canvas.palette])
        self.assertEqual(reloaded.distinct_indices(), canvas.distinct_indices())

    def test_reload_after_diffusion_keeps_exact_index_set(self):
        canvas = make_canvas(32, 12)
        PaintEngine(canvas, make_brush()).paint_error_diffusion(
            [(x + 0.5, 6.0, 0.3 + 0.5 * x / 31) for x in range(32)])
        base = tmp_project()
        save_project(canvas, base)
        reloaded = load_project(base)
        self.assertEqual(reloaded.distinct_indices(), canvas.distinct_indices())
        self.assertEqual(bytes(reloaded.raw_indices()), bytes(canvas.raw_indices()))


class IndexSemanticsTests(unittest.TestCase):
    def test_same_rgb_indices_have_distinct_editing_meaning(self):
        canvas = make_canvas(8, 4)
        canvas.set_index(0, 0, 1)
        canvas.set_index(1, 0, 6)  # same RGB as 1
        canvas.locked_indices.add(6)
        brush = make_brush(radius=3.5)
        PaintEngine(canvas, brush).paint_ordered([(0.5, 0.5, 1.0)])
        # Index 6 is locked and survives the stroke; index 1 is free and changes.
        self.assertEqual(canvas.get_index(1, 0), 6)
        self.assertNotEqual(canvas.get_index(0, 0), 1)

    def test_erasing_writes_transparent_index_not_background_rgb(self):
        canvas = make_canvas(8, 4)
        for x in range(8):
            canvas.set_index(x, 2, 3)
        eraser = make_brush(ramp=Ramp((canvas.transparent_index,)), radius=1.0)
        PaintEngine(canvas, eraser).paint_ordered([(3.5, 2.5, 1.0)])
        self.assertEqual(canvas.get_index(3, 2), canvas.transparent_index)
        # Neighbours untouched.
        self.assertEqual(canvas.get_index(1, 2), 3)

    def test_engine_never_invents_palette_entries(self):
        canvas = make_canvas(16, 16)
        ramp = Ramp((1, 2))
        brush = make_brush(ramp=ramp, radius=3.0)
        used = PaintEngine(canvas, brush).paint_ordered(
            [(7.5, 7.5, p / 10.0) for p in range(11)])
        self.assertTrue(used.issubset({0, 1, 2}))


if __name__ == "__main__":
    unittest.main()
