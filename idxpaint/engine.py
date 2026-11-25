"""Painting kernel operating strictly in palette-index space.

Two dithering modes are supported:

* ordered dither -- every touched pixel is decided independently against a
  Bayer threshold anchored to its absolute canvas coordinate;
* Floyd-Steinberg error diffusion -- a persistent residual buffer keyed by
  canvas coordinate lets a stroke be processed tile by tile in row-major
  order with byte-identical results to one-shot processing.

Palette-locked pixels are never overwritten.  When diffusion reaches one,
:class:`LockPolicy` decides whether the residual is dropped (RESTART) or
measured against the locked value and carried onward (CARRY).
"""

from __future__ import annotations

from .brush import AlphaPolicy, Brush, LockPolicy, ordered_index, ramp_position
from .canvas import IndexedCanvas


class PaintEngine:
    def __init__(self, canvas: IndexedCanvas, brush: Brush):
        self.canvas = canvas
        self.brush = brush
        self._error: dict[tuple[int, int], float] = {}
        # When set, diffusion is clipped to this rectangle; residuals that
        # would leave it are absorbed at the boundary instead of painting
        # pixels outside the requested region.
        self._region: tuple[int, int, int, int] | None = None
        # Last point of the previous input batch; lets batched strokes keep
        # the same cumulative arc length as a one-shot polyline.
        self._last_point: tuple[float, float, float] | None = None
        self._arc_length: float = 0.0

    def reset_stroke(self) -> None:
        self._last_point = None
        self._arc_length = 0.0
        self.reset_diffusion()

    def _stamp_centres(self, points: list[tuple[float, float, float]]
                       ) -> list[tuple[float, float, float]]:
        """Globally spaced stamp centres, stable across input batches."""
        import math
        if not points:
            return []
        if self._last_point is None:
            chain = list(points)
        else:
            chain = [self._last_point] + list(points)
        cum = [0.0]
        for (x0, y0, _), (x1, y1, _) in zip(chain, chain[1:]):
            cum.append(cum[-1] + math.hypot(x1 - x0, y1 - y0))
        total = cum[-1]
        if total == 0.0:
            self._last_point = points[-1]
            return [points[-1]]
        spacing = max(self.brush.spacing, 1e-9)
        first_k = 0 if self._arc_length == 0.0 else int(self._arc_length // spacing) + 1
        last_k = int((self._arc_length + total) // spacing)
        out: list[tuple[float, float, float]] = []
        seg = 0
        for k in range(first_k, last_k + 1):
            dist = k * spacing - self._arc_length
            while seg < len(chain) - 2 and cum[seg + 1] < dist:
                seg += 1
            seg_len = cum[seg + 1] - cum[seg]
            t = 0.0 if seg_len == 0.0 else (dist - cum[seg]) / seg_len
            x0, y0, p0 = chain[seg]
            x1, y1, p1 = chain[seg + 1]
            out.append((x0 + (x1 - x0) * t,
                        y0 + (y1 - y0) * t,
                        p0 + (p1 - p0) * t))
        self._arc_length += total
        self._last_point = points[-1]
        if not out or out[-1][:2] != points[-1][:2]:
            out.append(points[-1])
        return out

    # -- stroke rasterization ---------------------------------------------
    def build_targets(self, points: list[tuple[float, float, float]]
                      ) -> dict[tuple[int, int], tuple[float, float, float, float]]:
        """Rasterize a pressure stroke.

        Returns ``{(x, y): (ramp_position, coverage, centre_x, centre_y)}``.
        When stamps overlap, the strongest pressure and coverage win, so the
        result depends only on absolute canvas coordinates -- never on how
        points were batched.
        """
        targets: dict[tuple[int, int], tuple[float, float, float, float]] = {}
        for cx, cy, pressure in self._stamp_centres(points):
            position = ramp_position(pressure, self.brush.ramp)
            for x, y, cov in self.brush.stamp_pixels(cx, cy):
                if not self.canvas.in_bounds(x, y):
                    continue
                old = targets.get((x, y))
                # Canonical, order-independent merge: strongest pressure wins,
                # coverage only breaks ties.  Batching cannot change results.
                if old is None or (position, cov) > (old[0], old[1]):
                    targets[(x, y)] = (position, cov, cx, cy)
        return targets

    # -- alpha handling ----------------------------------------------------
    def _alpha_gate(self, x: int, y: int, coverage: float, ink_index: int,
                    centre: tuple[float, float] | None = None) -> int:
        existing = self.canvas.get_index(x, y)
        policy = self.brush.alpha_policy
        full = coverage >= 1.0 or (
            centre is not None
            and self.brush.is_fully_covered(x, y, centre[0], centre[1]))
        if full or policy is AlphaPolicy.OVERWRITE:
            return ink_index
        if policy is AlphaPolicy.KEEP_TRANSPARENT:
            return existing if existing == self.canvas.transparent_index else ink_index
        # DITHER: anchored threshold blends ink with whatever index is there,
        # the transparent index being just another (distinct) index.
        t = self.brush._dither.threshold(x, y)
        return ink_index if coverage > t else existing

    # -- ordered mode ------------------------------------------------------
    def paint_ordered(self, points: list[tuple[float, float, float]]) -> set[int]:
        targets = self.build_targets(points)
        used: set[int] = set()
        for (x, y), (position, cov, cx, cy) in targets.items():
            if self.canvas.is_locked(x, y):
                continue
            ink = ordered_index(self.brush, position, x, y)
            chosen = self._alpha_gate(x, y, cov, ink, (cx, cy))
            self.canvas.set_index(x, y, chosen)
            used.add(chosen)
        return used

    # -- error diffusion mode ---------------------------------------------
    def _ramp_coordinate_of(self, index: int) -> float | None:
        try:
            return float(self.brush.ramp.indices.index(index))
        except ValueError:
            return None

    def _diffuse(self, x: int, y: int, residual: float) -> None:
        from .dither import FLOYD_STEINBERG
        for dx, dy, w in FLOYD_STEINBERG:
            if dy == 0 and dx <= 0:
                continue
            nx, ny = x + dx, y + dy
            if self._region is not None:
                x0, y0, x1, y1 = self._region
                if not (x0 <= nx <= x1 and y0 <= ny <= y1):
                    continue  # absorb at the region boundary
            self._error[(nx, ny)] = self._error.get((nx, ny), 0.0) + residual * w

    def _process_cell(self, x: int, y: int,
                      targets: dict[tuple[int, int], tuple[float, float, float, float]]) -> None:
        residual = self._error.pop((x, y), 0.0)
        target = targets.get((x, y))
        if target is None:
            # Untouched pixels are never repainted.  Residual is carried over
            # them so it can reach a later stroke pixel (or be measured at a
            # lock), but it cannot by itself invent paint on blank canvas.
            if residual:
                self._diffuse(x, y, residual)
            return

        position, coverage, cx, cy = target
        locked = self.canvas.is_locked(x, y)
        ramp = self.brush.ramp

        if locked:
            if self.brush.lock_policy is LockPolicy.RESTART:
                return  # residual consumed and dropped: diffusion restarts
            # CARRY: measure error against the value the locked pixel shows.
            virtual = self._ramp_coordinate_of(self.canvas.get_index(x, y))
            if virtual is None:
                virtual = float(max(0, min(round(position), ramp.steps - 1)))
            self._diffuse(x, y, (position + residual) - virtual)
            return

        corrected = position + residual
        k = max(0, min(round(corrected), ramp.steps - 1))
        ink = ramp.at(k)
        chosen = self._alpha_gate(x, y, coverage, ink, (cx, cy))
        self.canvas.set_index(x, y, chosen)
        # Only diffuse the rounding error to cells that are themselves part of
        # the stroke; a residual that reaches untouched canvas is absorbed.
        virtual = self._ramp_coordinate_of(chosen)
        if virtual is None:  # alpha gate kept a non-ramp index (e.g. transparent)
            virtual = float(k)
        self._diffuse_targets(x, y, corrected - virtual, targets)

    def _diffuse_targets(self, x: int, y: int, residual: float, targets) -> None:
        from .dither import FLOYD_STEINBERG
        for dx, dy, w in FLOYD_STEINBERG:
            if dy == 0 and dx <= 0:
                continue
            nx, ny = x + dx, y + dy
            if (nx, ny) not in targets:
                continue
            if self._region is not None:
                x0, y0, x1, y1 = self._region
                if not (x0 <= nx <= x1 and y0 <= ny <= y1):
                    continue
            self._error[(nx, ny)] = self._error.get((nx, ny), 0.0) + residual * w

    def paint_error_diffusion(
        self,
        points: list[tuple[float, float, float]],
        region: tuple[int, int, int, int] | None = None,
    ) -> set[int]:
        """Diffuse over a rectangular ``(x0, y0, x1, y1)`` region (inclusive)."""
        targets = self.build_targets(points)
        if not targets:
            return set()
        if region is None:
            xs = [p[0] for p in targets]
            ys = [p[1] for p in targets]
            region = (min(xs), min(ys), max(xs), max(ys))
        x0, y0, x1, y1 = region
        before = set(self.canvas.distinct_indices())
        self._region = region
        try:
            for y in range(y0, y1 + 1):
                for x in range(x0, x1 + 1):
                    self._process_cell(x, y, targets)
        finally:
            self._region = None
        return self.canvas.distinct_indices() - before

    def paint_error_diffusion_tiled(
        self,
        points: list[tuple[float, float, float]],
        tile_width: int,
        tile_height: int,
    ) -> set[int]:
        """Diffuse split into row-major horizontal band tiles.

        Floyd-Steinberg only feeds forward (right and next row), so legal
        tile boundaries are horizontal bands of ``tile_height`` rows spanning
        the full width; the residual buffer persists between bands exactly as
        it does in one-shot processing, giving byte-identical output.
        """
        targets = self.build_targets(points)
        if not targets:
            return set()
        xs = [p[0] for p in targets]
        ys = [p[1] for p in targets]
        x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
        before = set(self.canvas.distinct_indices())
        self._region = (x0, y0, x1, y1)
        try:
            ty = y0
            while ty <= y1:
                y_end = min(ty + tile_height - 1, y1)
                for y in range(ty, y_end + 1):
                    for x in range(x0, x1 + 1):
                        self._process_cell(x, y, targets)
                ty += tile_height
        finally:
            self._region = None
        return self.canvas.distinct_indices() - before

    def reset_diffusion(self) -> None:
        self._error.clear()


def boundary_stripe_pollution(before: IndexedCanvas, after: IndexedCanvas,
                              rect: tuple[int, int, int, int],
                              side: str, width: int = 1) -> int:
    """Count changed indices in a stripe just outside a painted rect.

    ``side`` is one of ``top``, ``bottom``, ``left``, ``right``.  A nonzero
    count means paint residuals leaked across the region boundary.
    """
    x0, y0, x1, y1 = rect
    cells: list[tuple[int, int]] = []
    if side == "top":
        cells = [(x, y) for y in range(max(0, y0 - width), y0)
                 for x in range(x0, x1 + 1)]
    elif side == "bottom":
        cells = [(x, y) for y in range(y1 + 1, min(after.height, y1 + 1 + width))
                 for x in range(x0, x1 + 1)]
    elif side == "left":
        cells = [(x, y) for x in range(max(0, x0 - width), x0)
                 for y in range(y0, y1 + 1)]
    elif side == "right":
        cells = [(x, y) for x in range(x1 + 1, min(after.width, x1 + 1 + width))
                 for y in range(y0, y1 + 1)]
    else:
        raise ValueError(f"unknown side {side!r}")
    return sum(1 for x, y in cells
               if before.in_bounds(x, y) and before.get_index(x, y) != after.get_index(x, y))
