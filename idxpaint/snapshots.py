"""Re-export of the separate index, residual and palette snapshot types."""

from .diffusion import DiffusionSnapshot, ErrorSnapshot, ResidualSnapshot
from .history import ColorIndexMappingSnapshot, IndexMappingSnapshot
from .index_canvas import CanvasSnapshot, IndexCanvasSnapshot, IndexSnapshot
from .palette import PaletteSnapshot

__all__ = [
    "IndexSnapshot",
    "IndexCanvasSnapshot",
    "CanvasSnapshot",
    "ErrorSnapshot",
    "ResidualSnapshot",
    "DiffusionSnapshot",
    "PaletteSnapshot",
    "IndexMappingSnapshot",
    "ColorIndexMappingSnapshot",
]
