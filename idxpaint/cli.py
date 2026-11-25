"""Command line entry points: build demos and inspect raw index grids."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile

from .brush import AlphaPolicy, Brush, LockPolicy, Ramp
from .canvas import IndexedCanvas
from .engine import PaintEngine, boundary_stripe_pollution
from .evidence import collect_index_evidence, mapped_indices_equal
from .history import PaintHistory
from .palette import Palette, PaletteEntry
from .painting import IndexPainting
from .reorder import reorder_palette
from .storage import load_project, save_project

HEX = "0123456789abcdef"


def demo_palette() -> Palette:
    # Indices 0 and 6 share RGB but have different alpha/identity; index 1 is
    # the transparent index and is also visually distinct in meaning.
    return Palette([
        PaletteEntry(0, 0, 0, 0, "transparent"),        # 0
        PaletteEntry(30, 30, 48, 255, "ink-dark"),      # 1
        PaletteEntry(70, 70, 110, 255, "ink-mid"),      # 2
        PaletteEntry(120, 120, 170, 255, "ink-light"),  # 3
        PaletteEntry(200, 200, 230, 255, "ink-pale"),   # 4
        PaletteEntry(220, 60, 60, 255, "accent"),       # 5 locked later
        PaletteEntry(30, 30, 48, 255, "ink-dark-dup"),  # 6 same RGB as 1
        PaletteEntry(40, 160, 90, 255, "green"),        # 7
    ])


def cmd_demo(args: argparse.Namespace) -> None:
    palette = demo_palette()
    canvas = IndexedCanvas(48, 32, palette, transparent_index=0)
    canvas.locked_indices.add(5)

    # Locked red stripe through the middle, painted before the ink crosses it.
    for x in range(canvas.width):
        canvas.set_index(x, 15, 5)
        canvas.set_index(x, 16, 5)

    # Snapshot the two one-pixel stripes neighbouring the locked region so
    # pollution can be measured against the state *before* painting.
    stripe_rect = (0, 15, canvas.width - 1, 16)
    top_before = [canvas.get_index(x, 14) for x in range(canvas.width)]
    bottom_before = [canvas.get_index(x, 17) for x in range(canvas.width)]

    ramp = Ramp((1, 2, 3, 4))
    brush = Brush(ramp=ramp, radius=2.0, spacing=1.0, dither_order=3,
                  lock_policy=LockPolicy(args.lock_policy),
                  alpha_policy=AlphaPolicy(args.alpha_policy))
    engine = PaintEngine(canvas, brush)

    # Stroke whose band crosses the locked stripe, exercising the lock policy.
    points = [(2 + i * 0.5, 10 + (i % 9) * 0.3, i / 80.0) for i in range(81)]
    if args.mode == "ordered":
        engine.paint_ordered(points)
    else:
        engine.paint_error_diffusion_tiled(points, canvas.width, args.tile)

    # Soft translucent green stroke along the bottom.
    soft = Brush(ramp=Ramp((7,)), radius=2.5, soft_edge=0.8,
                 alpha_policy=AlphaPolicy(args.alpha_policy))
    PaintEngine(canvas, soft).paint_ordered(
        [(4 + i * 0.6, 26, 1.0) for i in range(60)])

    class _Snapshot:
        def __init__(self, src, top, bottom):
            self.src = src
            self.top, self.bottom = top, bottom

        def in_bounds(self, x, y):
            return self.src.in_bounds(x, y)

        def get_index(self, x, y):
            if y == 14:
                return self.top[x]
            if y == 17:
                return self.bottom[x]
            return self.src.get_index(x, y)

    before = _Snapshot(canvas, top_before, bottom_before)
    pollution = sum(
        boundary_stripe_pollution(before, canvas, stripe_rect, side, 1)
        for side in ("top", "bottom"))
    base = args.out
    png_path, json_path = save_project(canvas, base)
    print(f"wrote {png_path} and {json_path}")
    print(f"indices present: {sorted(canvas.distinct_indices())}")
    print(f"locked-stripe neighbour changes (boundary pollution): {pollution}")


def cmd_verify(args: argparse.Namespace) -> None:
    """Run index/palette/undo/export checks and write real evidence."""
    out_dir = args.out_dir or tempfile.mkdtemp(prefix="idxpaint-verify-")
    os.makedirs(out_dir, exist_ok=True)

    painting = IndexPainting(32, 16, palette="demo")
    ordered_used = painting.paint_gradient(
        1.5, 4.5, 30.5, 4.5, mode="ordered"
    )
    before_diffusion = painting.canvas.snapshot()
    diffusion_new_distinct = painting.paint_gradient(
        1.5, 11.5, 30.5, 11.5, mode="diffusion"
    )
    diffusion_changes = painting.canvas.changed_cells(before_diffusion)
    diffusion_indices_used = sorted({new for _, _, _, new in diffusion_changes})
    if len(diffusion_indices_used) < 3:
        raise RuntimeError("diffusion gradient did not write a multi-index ramp")
    diffusion_rows = sorted({y for _, y, _, _ in diffusion_changes})
    diffusion_row_signatures = {
        str(y): [painting.canvas.get_index(x, y) for x in range(2, 30)]
        for y in diffusion_rows
    }

    base = os.path.join(out_dir, "index_painting")
    png_path, project_path = painting.save_project(base)
    reloaded = load_project(base)
    if bytes(reloaded.raw_indices()) != bytes(painting.canvas.raw_indices()):
        raise RuntimeError("reloaded indices do not match painted indices")

    # Build real pending next-row diffusion state, then reorder palette and
    # undo.  This is the executable proof that indices and residuals restore
    # together.
    probe = IndexPainting(16, 8, palette="demo")
    engine = probe.engine
    points = [(x + 0.5, 2.5, 0.8) for x in range(16)]
    targets = engine.build_targets(points)
    engine._region = (0, 0, 15, 7)
    for x in range(16):
        engine._process_cell(x, 1, targets)
    before_indices = bytes(probe.canvas.raw_indices())
    before_errors = engine.snapshot_errors()
    permutation = [3, 2, 7, 0, 1, 6, 5, 4]
    mapping = probe.reorder_palette(permutation, "keep_appearance")
    after_reorder_indices = bytes(probe.canvas.raw_indices())
    mapped_equivalent = mapped_indices_equal(
        before_indices, after_reorder_indices, mapping
    )
    if not mapped_equivalent:
        raise RuntimeError("palette reorder mapping does not explain index values")
    if probe.canvas.transparent_index != mapping[0]:
        raise RuntimeError("transparent index did not follow palette mapping")

    probe.undo()
    undo_indices_match = bytes(probe.canvas.raw_indices()) == before_indices
    undo_errors_match = engine.snapshot_errors() == before_errors
    if not undo_indices_match or not undo_errors_match:
        raise RuntimeError("undo failed to restore indices or diffusion residuals")

    evidence = {
        "status": "passed",
        "output_directory": os.path.abspath(out_dir),
        "graphical_entry": "viewer/viewer.html",
        "ordered_indices_used": sorted(ordered_used),
        "diffusion_indices_used": diffusion_indices_used,
        "diffusion_new_distinct_indices": sorted(diffusion_new_distinct),
        "diffusion_changed_cell_count": len(diffusion_changes),
        "diffusion_row_signatures": diffusion_row_signatures,
        "export_files": {
            "png": os.path.abspath(png_path),
            "project_json": os.path.abspath(project_path),
        },
        "reload_matches": True,
        "palette_undo_check": {
            "permutation": permutation,
            "mapping": {str(k): v for k, v in mapping.items()},
            "mapped_indices_equivalent": mapped_equivalent,
            "transparent_index_before": 0,
            "transparent_index_after_reorder": mapping[0],
            "undo_restores_indices": undo_indices_match,
            "undo_restores_next_row_diffusion": undo_errors_match,
            "pending_residual_count": len(before_errors.residuals),
        },
        "painting": painting.evidence(),
    }
    evidence_path = os.path.join(out_dir, "evidence.json")
    with open(evidence_path, "w", encoding="utf-8") as f:
        json.dump(evidence, f, indent=2, ensure_ascii=False)
    mapping_path = os.path.join(out_dir, "export_mapping.json")
    with open(mapping_path, "w", encoding="utf-8") as f:
        json.dump(
            {str(k): list(v) for k, v in painting.export_mapping().items()},
            f, indent=2, ensure_ascii=False,
        )
    print(json.dumps({
        "status": "passed",
        "evidence": evidence_path,
        "export_mapping": mapping_path,
        "project": project_path,
        "pending_residuals": len(before_errors.residuals),
    }, indent=2))


def cmd_inspect(args: argparse.Namespace) -> None:
    canvas = load_project(args.project)
    x0, y0, x1, y1 = args.rect
    x1 = min(x1, canvas.width - 1)
    y1 = min(y1, canvas.height - 1)
    lines = []
    for y in range(y0, y1 + 1):
        lines.append(" ".join(
            HEX[canvas.get_index(x, y)] for x in range(x0, x1 + 1)))
    report = {
        "size": [canvas.width, canvas.height],
        "transparent_index": canvas.transparent_index,
        "locked_indices": sorted(canvas.locked_indices),
        "distinct_indices": sorted(canvas.distinct_indices()),
        "rect": [x0, y0, x1, y1],
        "index_grid_hex": lines,
        "palette": [
            {"index": i, "rgba": list(e.rgba), "name": e.name}
            for i, e in enumerate(canvas.palette)
        ],
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="idxpaint")
    sub = parser.add_subparsers(dest="command", required=True)

    d = sub.add_parser("demo", help="generate a demo indexed painting")
    d.add_argument("--out", default="examples/demo")
    d.add_argument("--mode", choices=["ordered", "diffusion"], default="ordered")
    d.add_argument("--lock-policy", choices=[p.value for p in LockPolicy],
                   default="restart")
    d.add_argument("--alpha-policy", choices=[p.value for p in AlphaPolicy],
                   default="dither")
    d.add_argument("--tile", type=int, default=16)
    d.set_defaults(func=cmd_demo)

    i = sub.add_parser("inspect", help="print raw palette-index data")
    i.add_argument("project")
    i.add_argument("--rect", type=int, nargs=4,
                   metavar=("X0", "Y0", "X1", "Y1"), default=[0, 0, 15, 15])
    i.set_defaults(func=cmd_inspect)

    v = sub.add_parser(
        "verify",
        help="paint in a clean/temp directory and write index/export evidence",
    )
    v.add_argument("--out-dir", default=None,
                   help="new/empty evidence directory; defaults to a temp directory")
    v.set_defaults(func=cmd_verify)

    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
