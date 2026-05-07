"""runscroll — turn one batch run into one scrollable HTML report."""

from .asset_writer import AssetWriter, LocalAssetWriter
from .collector import Collector

__version__ = "1.0.0"

__all__ = [
    "AssetWriter",
    "Collector",
    "LocalAssetWriter",
    "__version__",
]
