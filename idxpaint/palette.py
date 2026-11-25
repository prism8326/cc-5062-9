"""Indexed palette.

A palette is an *ordered* list of entries.  An entry's position in that list is
its index and is the only identity a stored pixel ever holds.  Two entries may
share the exact same RGB(A) yet remain distinct indices with distinct editing
meaning (for example a locked overlay colour versus a normal one).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PaletteEntry:
    r: int
    g: int
    b: int
    a: int = 255
    name: str = ""

    @property
    def rgb(self) -> tuple[int, int, int]:
        return (self.r, self.g, self.b)

    @property
    def rgba(self) -> tuple[int, int, int, int]:
        return (self.r, self.g, self.b, self.a)


class Palette:
    def __init__(self, entries: list[PaletteEntry] | None = None):
        self._entries: list[PaletteEntry] = list(entries or [])

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self):
        return iter(self._entries)

    def __getitem__(self, index: int) -> PaletteEntry:
        return self._entries[index]

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Palette) and other._entries == self._entries

    def index(self, entry: PaletteEntry) -> int:
        return self._entries.index(entry)

    def add(self, entry: PaletteEntry) -> int:
        self._entries.append(entry)
        return len(self._entries) - 1

    def set_color(self, index: int, rgba: tuple[int, int, int, int]) -> None:
        """Repaint an entry in place; index identity is preserved."""
        r, g, b, a = rgba
        old = self._entries[index]
        self._entries[index] = PaletteEntry(r, g, b, a, old.name)

    def entries(self) -> list[PaletteEntry]:
        return list(self._entries)

    def to_rgba_table(self) -> list[tuple[int, int, int, int]]:
        return [e.rgba for e in self._entries]

    def reorder(self, permutation: list[int]) -> "Palette":
        """Return a new palette whose entry order follows *permutation*.

        ``permutation[i]`` is the old index that now lives at position ``i``.
        Entries themselves are moved untouched, so duplicate-RGB entries keep
        their identity (lock flags, names, alpha) rather than being merged.
        """
        if sorted(permutation) != list(range(len(self._entries))):
            raise ValueError("permutation must be a bijection over palette indices")
        return Palette([self._entries[old] for old in permutation])

    @staticmethod
    def from_colors(colors: list[tuple[int, int, int] | tuple[int, int, int, int]]) -> "Palette":
        entries = []
        for c in colors:
            if len(c) == 3:
                entries.append(PaletteEntry(c[0], c[1], c[2]))
            else:
                entries.append(PaletteEntry(c[0], c[1], c[2], c[3]))
        return Palette(entries)
