"""Dithering primitives anchored to absolute canvas coordinates.

Ordered dither thresholds are evaluated with the *canvas* (x, y) of each
pixel, so the pattern phase never depends on brush radius, stroke batching,
tile origin or on-screen zoom.
"""

from __future__ import annotations


def bayer_matrix(order: int) -> list[list[int]]:
    """Return a 2**order x 2**order Bayer matrix holding values in [0, n*n)."""
    if order < 1:
        raise ValueError("Bayer order must be >= 1")
    m = [[0]]
    size = 1
    for _ in range(order):
        n = size
        base = m
        new = [[0] * (2 * n) for _ in range(2 * n)]
        for y in range(n):
            for x in range(n):
                v = 4 * base[y][x]
                new[y][x] = v
                new[y][x + n] = v + 2
                new[y + n][x] = v + 3
                new[y + n][x + n] = v + 1
        m = new
        size *= 2
    return m


class OrderedDither:
    def __init__(self, order: int = 3):
        self.matrix = bayer_matrix(order)
        self.n = len(self.matrix)
        # Thresholds centred on 0.5, spread over [0, 1).
        self._scale = 1.0 / (self.n * self.n)

    def threshold(self, x: int, y: int) -> float:
        """Anchored threshold in (0, 1) for absolute canvas coordinate."""
        v = self.matrix[y % self.n][x % self.n]
        return (v + 0.5) * self._scale

    def pick(self, position: float, x: int, y: int) -> int:
        """Round *position* (a fractional ramp coordinate) by anchored threshold.

        Given ``k = floor(position)`` and ``f = position - k``, the pixel
        takes the upper step only when the canvas-anchored threshold is below
        ``f``.  Two pixels at the same canvas coordinate always see the same
        threshold regardless of how the stroke was split.
        """
        k = int(position)
        f = position - k
        return k + (1 if f > self.threshold(x, y) else 0)


# Floyd-Steinberg diffusion weights (dx, dy, weight).
FLOYD_STEINBERG = [
    (1, 0, 7 / 16),
    (-1, 1, 3 / 16),
    (0, 1, 5 / 16),
    (1, 1, 1 / 16),
]


class DitherDecision:
    """Pure index/error decision boundary shared by painting front ends.

    It knows about coordinate-anchored ordered thresholds and finite ramps,
    but not about canvas storage, palettes or UI frameworks.
    """

    def __init__(self, order: int = 3):
        self.ordered_dither = OrderedDither(order)

    def threshold(self, x: int, y: int) -> float:
        return self.ordered_dither.threshold(x, y)

    def ordered_coordinate(self, position: float, x: int, y: int) -> int:
        return self.ordered_dither.pick(position, x, y)

    def ordered_index(self, ramp, position: float, x: int, y: int) -> int:
        return ramp.at(self.ordered_coordinate(position, x, y))

    def diffusion_step(
        self, ramp, position: float, residual: float = 0.0
    ) -> tuple[int, int, float]:
        """Return ``(palette_index, ramp_coordinate, quantization_error)``."""
        corrected = position + residual
        coordinate = max(0, min(round(corrected), ramp.steps - 1))
        index = ramp.at(coordinate)
        return index, coordinate, corrected - coordinate


DitherPlanner = DitherDecision
DitherStrategy = DitherDecision
