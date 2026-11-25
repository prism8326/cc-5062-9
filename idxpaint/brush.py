"""Brushes that emit palette indices.

A :class:`Ramp` is an ordered sequence of palette indices ("colour steps").
Pressure selects a fractional position inside the ramp; dithering then decides
the concrete index of every touched pixel.  Everything downstream stays in
index space -- no RGB value is ever computed by the brush.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum

from .dither import FLOYD_STEINBERG, OrderedDither


class LockPolicy(Enum):
    """What error diffusion does when a target pixel is palette-locked."""

    RESTART = "restart"   # drop the residual; diffusion restarts past the lock
    CARRY = "carry"       # measure error against the locked value and carry it on


class AlphaPolicy(Enum):
    """How a brush with sub-opaque coverage treats the transparent index."""

    DITHER = "dither"                 # ordered blend between transparent and ink
    KEEP_TRANSPARENT = "keep"         # transparent pixels stay transparent
    OVERWRITE = "overwrite"           # coverage is ignored; ink fully replaces


@dataclass(frozen=True)
class Ramp:
    indices: tuple[int, ...]

    def __post_init__(self):
        if len(self.indices) < 1:
            raise ValueError("ramp needs at least one palette index")
        for i in self.indices:
            if i < 0:
                raise ValueError("palette indices must be non-negative")
        if len(set(self.indices)) != len(self.indices):
            raise ValueError("ramp steps must be distinct indices")

    @property
    def steps(self) -> int:
        return len(self.indices)

    def at(self, position: int) -> int:
        return self.indices[max(0, min(position, self.steps - 1))]


@dataclass
class Brush:
    ramp: Ramp
    radius: float = 1.0
    spacing: float = 1.0
    soft_edge: float = 0.0          # 0 = hard disc, 1 = fully soft falloff
    dither_order: int = 3
    lock_policy: LockPolicy = LockPolicy.RESTART
    alpha_policy: AlphaPolicy = AlphaPolicy.DITHER
    shape: str = "disc"             # "disc" or "square"
    _dither: OrderedDither = field(init=False, repr=False)

    def __post_init__(self):
        self._dither = OrderedDither(self.dither_order)

    # -- geometry ----------------------------------------------------------
    def is_fully_covered(self, x: int, y: int, cx: float, cy: float) -> bool:
        """True when pixel (x,y) lies inside the hard core of a stamp."""
        r = max(self.radius, 0.01)
        # Even a fully soft brush keeps a one-pixel hard core at its centre.
        core_r = max(r * (1.0 - self.soft_edge), 0.5)
        if self.shape == "square":
            return abs(x - cx) <= core_r and abs(y - cy) <= core_r
        d = math.hypot(x + 0.5 - cx, y + 0.5 - cy)
        return d <= core_r

    def stamp_pixels(self, cx: float, cy: float) -> list[tuple[int, int, float]]:
        """Rasterize one stamp; returns (x, y, coverage) in canvas coordinates."""
        r = max(self.radius, 0.01)
        x0 = math.floor(cx - r - 0.5)
        x1 = math.ceil(cx + r + 0.5)
        y0 = math.floor(cy - r - 0.5)
        y1 = math.ceil(cy + r + 0.5)
        out: list[tuple[int, int, float]] = []
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                if self.shape == "square":
                    cov = 1.0 if abs(x - cx) <= r and abs(y - cy) <= r else 0.0
                else:
                    d = math.hypot(x + 0.5 - cx, y + 0.5 - cy)
                    if d > r:
                        continue
                    if self.soft_edge <= 0.0 or d <= r * (1.0 - self.soft_edge):
                        cov = 1.0
                    else:
                        inner = r * (1.0 - self.soft_edge)
                        cov = max(0.05, 1.0 - (d - inner) / max(r - inner, 1e-9))
                if cov > 0.0:
                    out.append((x, y, cov))
        return out


def ramp_position(pressure: float, ramp: Ramp) -> float:
    """Map pressure in [0, 1] to a fractional ramp coordinate in [0, steps-1]."""
    p = max(0.0, min(1.0, pressure))
    return p * (ramp.steps - 1)


def ordered_index(brush: Brush, position: float, x: int, y: int) -> int:
    k = brush._dither.pick(position, x, y)
    return brush.ramp.at(k)


def fs_weights() -> list[tuple[int, int, float]]:
    return list(FLOYD_STEINBERG)
