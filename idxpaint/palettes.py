"""Named colour tables available to both CLI and graphical callers."""

from __future__ import annotations

from .palette import Palette, PaletteEntry


def demo_palette() -> Palette:
    # Indices 0 and 6 share RGB but have different alpha/identity.
    return Palette([
        PaletteEntry(0, 0, 0, 0, "transparent"),
        PaletteEntry(30, 30, 48, 255, "ink-dark"),
        PaletteEntry(70, 70, 110, 255, "ink-mid"),
        PaletteEntry(120, 120, 170, 255, "ink-light"),
        PaletteEntry(200, 200, 230, 255, "ink-pale"),
        PaletteEntry(220, 60, 60, 255, "accent"),
        PaletteEntry(30, 30, 48, 255, "ink-dark-dup"),
        PaletteEntry(40, 160, 90, 255, "green"),
    ])


def grayscale_palette() -> Palette:
    return Palette([
        PaletteEntry(0, 0, 0, 0, "transparent"),
        *[
            PaletteEntry(v, v, v, 255, f"gray-{i + 1}")
            for i, v in enumerate((28, 64, 104, 148, 190, 224, 250))
        ],
    ])


def sepia_palette() -> Palette:
    colors = (
        (43, 32, 24),
        (82, 58, 39),
        (126, 91, 58),
        (171, 132, 86),
        (214, 184, 139),
        (239, 220, 181),
        (255, 246, 220),
    )
    return Palette([
        PaletteEntry(0, 0, 0, 0, "transparent"),
        *[PaletteEntry(r, g, b, 255, f"sepia-{i + 1}") for i, (r, g, b) in enumerate(colors)],
    ])


def spectrum_palette() -> Palette:
    colors = (
        (35, 38, 66),
        (67, 70, 128),
        (72, 123, 184),
        (72, 178, 163),
        (141, 205, 105),
        (245, 205, 82),
        (229, 87, 72),
    )
    return Palette([
        PaletteEntry(0, 0, 0, 0, "transparent"),
        *[PaletteEntry(r, g, b, 255, f"spectrum-{i + 1}") for i, (r, g, b) in enumerate(colors)],
    ])


PALETTE_TABLES = {
    "demo": demo_palette,
    "grayscale": grayscale_palette,
    "sepia": sepia_palette,
    "spectrum": spectrum_palette,
}


def get_palette_table(name: str | Palette) -> Palette:
    if isinstance(name, Palette):
        return name
    try:
        return PALETTE_TABLES[name]()
    except KeyError as exc:
        raise ValueError(
            f"unknown palette table {name!r}; choose from {sorted(PALETTE_TABLES)}"
        ) from exc
