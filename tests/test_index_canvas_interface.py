import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from idxpaint import (
    DiffusionCursor,
    IndexCanvas,
    IndexPainting,
    IndexSnapshot,
    PaintHistory,
    PaletteView,
    mapped_indices_equal,
)
from idxpaint.reorder import reorder_palette
from tests._helpers import make_brush, make_canvas


class IndexCanvasInterfaceTests(unittest.TestCase):
    def test_palette_free_canvas_stores_and_restores_only_indices(self):
        canvas = IndexCanvas(4, 3, transparent_index=0, color_count=3)
        canvas.set_index(1, 1, 2)
        snapshot = canvas.snapshot()
        self.assertIsInstance(snapshot, IndexSnapshot)
        self.assertEqual(snapshot.pixels[1 * 4 + 1], 2)

        canvas.set_index(1, 1, 1)
        canvas.restore_indices(snapshot)
        self.assertEqual(canvas.get_index(1, 1), 2)
        self.assertEqual(canvas.version, snapshot.revision + 1)

    def test_invalid_index_is_rejected_by_interface(self):
        canvas = IndexCanvas(2, 2, color_count=2)
        with self.assertRaises(ValueError):
            canvas.set_index(0, 0, 2)

    def test_palette_view_export_maps_indices_to_rgba(self):
        canvas = make_canvas(2, 2)
        view = PaletteView(canvas.palette)
        self.assertEqual(view.rgba(0), (0, 0, 0, 0))
        self.assertEqual(view.export_mapping()[1], canvas.palette[1].rgba)
        self.assertEqual(view.css_color(1), "rgba(20, 20, 30, 1.000)")


class SnapshotUndoTests(unittest.TestCase):
    def _pending_diffusion(self):
        canvas = make_canvas(16, 8)
        from idxpaint.engine import PaintEngine
        engine = PaintEngine(canvas, make_brush(radius=1.0))
        points = [(x + 0.5, 2.5, 0.8) for x in range(16)]
        targets = engine.build_targets(points)
        engine._region = (0, 0, 15, 7)
        for x in range(16):
            engine._process_cell(x, 1, targets)
        return canvas, engine

    def test_palette_reorder_undo_restores_indices_and_next_row_errors(self):
        canvas, engine = self._pending_diffusion()
        history = PaintHistory()
        before_indices = bytes(canvas.raw_indices())
        before_errors = engine.snapshot_errors()
        self.assertTrue(before_errors.residuals)

        history.checkpoint("reorder", canvas, engine.diffusion_cursor)
        permutation = [3, 2, 7, 0, 1, 6, 5, 4]
        mapping = reorder_palette(canvas, permutation, "keep_appearance")
        after = bytes(canvas.raw_indices())
        self.assertTrue(mapped_indices_equal(before_indices, after, mapping))
        self.assertEqual(canvas.transparent_index, mapping[0])

        history.undo(canvas, engine.diffusion_cursor)
        self.assertEqual(bytes(canvas.raw_indices()), before_indices)
        self.assertEqual(engine.snapshot_errors(), before_errors)
        self.assertEqual(canvas.transparent_index, 0)

    def test_error_snapshot_is_independent_of_restoring_index_snapshot(self):
        cursor = DiffusionCursor()
        cursor.add(2, 3, 0.25)
        snapshot = cursor.snapshot()
        cursor.add(3, 3, -0.5)
        cursor.restore(snapshot)
        self.assertAlmostEqual(cursor.get(2, 3), 0.25)
        self.assertEqual(cursor.get(3, 3), 0.0)


class FacadeAndEvidenceTests(unittest.TestCase):
    def test_index_painting_selects_table_paints_and_exports_mapping(self):
        painting = IndexPainting(20, 8, palette="spectrum")
        painting.paint_gradient(1.5, 4, 18.5, 4, mode="ordered")
        evidence = painting.evidence()
        self.assertEqual(evidence["width"], 20)
        self.assertIn("export_mapping", evidence)
        self.assertTrue(any(v != 0 for v in painting.canvas.raw_indices()))

    def test_verify_cli_runs_in_clean_directory(self):
        with tempfile.TemporaryDirectory() as root:
            out = os.path.join(root, "evidence")
            repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            run = subprocess.run(
                [sys.executable, "-I", os.path.join(repo, "run.py"),
                 "verify", "--out-dir", out],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            with open(os.path.join(out, "evidence.json"), encoding="utf-8") as f:
                evidence = json.load(f)
            self.assertEqual(evidence["status"], "passed")
            self.assertGreaterEqual(len(evidence["diffusion_indices_used"]), 3)
            self.assertGreater(evidence["diffusion_changed_cell_count"], 20)
            check = evidence["palette_undo_check"]
            self.assertTrue(check["mapped_indices_equivalent"])
            self.assertTrue(check["undo_restores_indices"])
            self.assertTrue(check["undo_restores_next_row_diffusion"])
            self.assertGreater(check["pending_residual_count"], 0)


if __name__ == "__main__":
    unittest.main()
