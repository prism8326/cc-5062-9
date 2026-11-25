import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from idxpaint.reorder import reorder_palette
from tests._helpers import make_canvas


class ReorderTests(unittest.TestCase):
    def _painted(self):
        canvas = make_canvas(12, 8)
        canvas.locked_indices.add(5)
        for x in range(12):
            canvas.set_index(x, 3, 1)
            canvas.set_index(x, 4, 5)
        return canvas

    def test_keep_appearance_preserves_rgba_at_every_pixel(self):
        canvas = self._painted()
        before = [canvas.palette[canvas.get_index(x, 3)].rgba for x in range(12)]
        permutation = [3, 2, 7, 0, 1, 6, 5, 4]  # arbitrary bijection
        reorder_palette(canvas, permutation, "keep_appearance")
        after = [canvas.palette[canvas.get_index(x, 3)].rgba for x in range(12)]
        self.assertEqual(before, after)
        # Stored numbers did move.
        self.assertNotEqual(canvas.get_index(0, 3), 1)
        # The lock moved with its entry.
        old5_new = permutation.index(5)
        self.assertIn(old5_new, canvas.locked_indices)
        self.assertEqual(canvas.get_index(0, 4), old5_new)

    def test_keep_identity_preserves_stored_indices(self):
        canvas = self._painted()
        stored_before = bytes(canvas.raw_indices())
        permutation = [7, 6, 5, 4, 3, 2, 1, 0]
        reorder_palette(canvas, permutation, "keep_identity")
        self.assertEqual(bytes(canvas.raw_indices()), stored_before)
        # Entry 5 is now whatever was moved to position 5 -- appearance may
        # change, but the handwriting still addresses index 5 explicitly.
        self.assertEqual(canvas.get_index(0, 4), 5)
        self.assertEqual(canvas.locked_indices, {5})

    def test_duplicate_rgb_entries_are_not_merged(self):
        canvas = make_canvas(6, 2)
        canvas.set_index(0, 0, 1)
        canvas.set_index(1, 0, 6)  # identical RGB to 1, different identity
        self.assertEqual(canvas.palette[1].rgb, canvas.palette[6].rgb)
        permutation = list(range(8))
        permutation[1], permutation[6] = permutation[6], permutation[1]
        mapping = reorder_palette(canvas, permutation, "keep_appearance")
        self.assertEqual(canvas.get_index(0, 0), mapping[1])
        self.assertEqual(canvas.get_index(1, 0), mapping[6])
        self.assertNotEqual(mapping[1], mapping[6])
        self.assertEqual(canvas.palette[mapping[1]].rgba,
                         canvas.palette[mapping[6]].rgba)

    def test_invalid_permutation_rejected(self):
        canvas = make_canvas(4, 4)
        with self.assertRaises(ValueError):
            reorder_palette(canvas, [0, 0, 1, 2, 3, 4, 5, 6], "keep_appearance")


if __name__ == "__main__":
    unittest.main()
