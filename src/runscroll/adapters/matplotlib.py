"""matplotlib Figure adapter — Figure -> PNG bytes.

The ``import matplotlib`` at module top is intentional: missing matplotlib
surfaces here as ImportError, which the dispatch layer translates into a
friendly "install with `pip install runscroll[matplotlib]`" message.
"""
from __future__ import annotations

import io
from typing import Any

import matplotlib  # noqa: F401  surfaces ImportError on missing matplotlib


def fig_to_png_bytes(
    fig: Any,
    dpi: int = 100,
    bbox_inches: str = "tight",
    facecolor: str = "white",
) -> bytes:
    """Encode a matplotlib Figure to PNG bytes.

    Defaults are chosen for log-friendly output: 100 DPI is sharp enough
    for screen reading, ``tight`` bbox crops marginalia, white facecolor
    keeps the image readable on dark and light report themes.
    """
    buf = io.BytesIO()
    fig.savefig(
        buf,
        format="png",
        dpi=dpi,
        bbox_inches=bbox_inches,
        facecolor=facecolor,
        edgecolor="none",
    )
    return buf.getvalue()


def close_figure(fig: Any) -> None:
    """Release a matplotlib Figure's resources.

    The moulder pipeline that seeded runscroll consistently called
    ``plt.close(fig)`` after every save; we absorb that pattern into the
    library so users don't have to.
    """
    import matplotlib.pyplot as plt

    plt.close(fig)
