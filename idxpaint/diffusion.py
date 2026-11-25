"""Independent residual cursor for Floyd-Steinberg diffusion.

The cursor is deliberately separate from the index matrix: a canvas snapshot
can restore the painted indices while an :class:`ErrorSnapshot` restores the
pending residuals that feed the current/next row.  History records pair the
two at undo boundaries without storing residuals inside pixel data.
"""

from __future__ import annotations

from dataclasses import dataclass

from .dither import FLOYD_STEINBERG


@dataclass(frozen=True)
class ErrorSnapshot:
    residuals: tuple[tuple[int, int, float], ...] = ()
    region: tuple[int, int, int, int] | None = None

    def as_dict(self) -> dict[tuple[int, int], float]:
        return {(x, y): value for x, y, value in self.residuals}


# Descriptive aliases for callers/tests using the requirement's wording.
ResidualSnapshot = ErrorSnapshot
DiffusionSnapshot = ErrorSnapshot


class DiffusionCursor:
    """Row-major error-propagation state independent of any canvas instance."""

    def __init__(
        self,
        errors: dict[tuple[int, int], float] | None = None,
        region: tuple[int, int, int, int] | None = None,
    ):
        self.errors: dict[tuple[int, int], float] = dict(errors or {})
        self.region = region

    def get(self, x: int, y: int) -> float:
        return self.errors.get((x, y), 0.0)

    def pop(self, x: int, y: int) -> float:
        return self.errors.pop((x, y), 0.0)

    def add(self, x: int, y: int, value: float) -> None:
        if value:
            self.errors[(x, y)] = self.errors.get((x, y), 0.0) + value

    def clear(self) -> None:
        self.errors.clear()
        self.region = None

    def pending_coordinates(self) -> list[tuple[int, int]]:
        return sorted(self.errors)

    def next_row_residuals(self, y: int) -> dict[int, float]:
        """Residuals currently waiting on row ``y`` (typically y + 1)."""
        return {x: value for (x, row), value in self.errors.items() if row == y}

    def propagate(
        self,
        x: int,
        y: int,
        residual: float,
        *,
        targets: dict | None = None,
        region: tuple[int, int, int, int] | None = None,
        weights=FLOYD_STEINBERG,
    ) -> None:
        active_region = self.region if region is None else region
        for dx, dy, weight in weights:
            if dy == 0 and dx <= 0:
                continue
            nx, ny = x + dx, y + dy
            if targets is not None and (nx, ny) not in targets:
                continue
            if active_region is not None:
                x0, y0, x1, y1 = active_region
                if not (x0 <= nx <= x1 and y0 <= ny <= y1):
                    continue
            self.add(nx, ny, residual * weight)

    # -- snapshots -----------------------------------------------------------
    def snapshot(self) -> ErrorSnapshot:
        return ErrorSnapshot(
            residuals=tuple(
                (x, y, value) for (x, y), value in sorted(self.errors.items())
            ),
            region=self.region,
        )

    def error_snapshot(self) -> ErrorSnapshot:
        return self.snapshot()

    def restore(self, snapshot: ErrorSnapshot) -> None:
        if not isinstance(snapshot, ErrorSnapshot):
            raise TypeError("expected an ErrorSnapshot")
        self.errors = snapshot.as_dict()
        self.region = snapshot.region

    def restore_snapshot(self, snapshot: ErrorSnapshot) -> None:
        self.restore(snapshot)


# Wording-level aliases.
ErrorPropagationCursor = DiffusionCursor
ResidualState = DiffusionCursor
ErrorState = DiffusionCursor
