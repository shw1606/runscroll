"""plotly Figure adapter — interactive embed (handoff §8.3).

Killer-value reason this exists: a plotly figure rendered via ``to_html``
ships zoom / pan / hover tooltips inside a single self-contained file.
matplotlib can't give that.

Two embed strategies match runscroll's two modes:

- **inline**: the plotly.js bundle (~5 MiB) is inlined ONCE on the first
  add_figure(plotly_fig) call. Subsequent figures emit only their per-plot
  script + div. The Collector tracks ``_plotly_bundle_emitted`` so we never
  duplicate the bundle.
- **directory**: the bundle is written to ``assets/plotly.min.js`` once and
  referenced via ``<script src="assets/plotly.min.js">``.

We pass ``include_mathjax=False`` to keep the bundle from pulling in MathJax
(which would itself try to fetch fonts from a CDN at runtime).
"""
from __future__ import annotations

from typing import Any, Tuple

import plotly  # noqa: F401  surfaces ImportError on missing plotly
import plotly.io as pio


def is_plotly_figure(obj: Any) -> bool:
    cls = type(obj)
    if not cls.__module__.startswith("plotly."):
        return False
    name = cls.__qualname__
    return name == "Figure" or name.endswith(".Figure")


def figure_to_html_with_inline_bundle(fig: Any) -> str:
    """Return the figure's HTML with the plotly.js bundle inlined.

    The output starts with the bundle's ``<script>`` tag(s) followed by the
    plot's div + per-plot script. Use this for the first plotly figure in
    an inline-mode report.
    """
    return pio.to_html(
        fig,
        include_plotlyjs="inline",
        include_mathjax=False,
        full_html=False,
    )


def figure_to_html_div_only(fig: Any) -> str:
    """Return the figure's HTML *without* the bundle — assumes plotly.js
    has already been loaded into the page (either inlined earlier or
    referenced via a separate <script src>)."""
    return pio.to_html(
        fig,
        include_plotlyjs=False,
        include_mathjax=False,
        full_html=False,
    )


def get_plotlyjs_bundle() -> str:
    """Return the plotly.js source string (used by directory mode to
    write ``assets/plotly.min.js`` once per report)."""
    from plotly.offline import get_plotlyjs

    return get_plotlyjs()
