"""Tests for plotly figure embedding (Step 11)."""
from __future__ import annotations

import re
import sys

import pytest

from runscroll import Collector


def _make_plotly_fig():
    go = pytest.importorskip("plotly.graph_objects")
    return go.Figure(go.Scatter(x=[1, 2, 3], y=[1, 4, 9]))


# ---------------------------------------------------------------------------
# Inline mode: bundle inlined exactly once across multiple plotly figures.
# ---------------------------------------------------------------------------

def test_plotly_inline_basic(tmp_path):
    fig = _make_plotly_fig()
    p = tmp_path / "x.html"
    with Collector(p) as c:
        c.add_figure(fig, title="Plot", description="example")
    content = p.read_text()
    assert "rs-figure-plotly" in content
    assert "Plot" in content
    assert "example" in content
    # plotly.js bundle is large — sanity-check it's actually inline.
    assert len(content) > 1_000_000  # 1 MiB+


def test_plotly_inline_bundle_emitted_once_for_multiple_figs(tmp_path):
    """Two plotly figures should embed the bundle's <script> only once.
    The plotly.js source contains the marker comment 'plotly.js v' — we
    count its occurrences as a proxy for bundle copies."""
    fig1 = _make_plotly_fig()
    fig2 = _make_plotly_fig()
    p = tmp_path / "x.html"
    with Collector(p) as c:
        c.add_figure(fig1)
        c.add_figure(fig2)
    content = p.read_text()
    bundle_markers = content.count("plotly.js v")
    # The marker appears once in the bundle banner. With two figures and
    # de-duplication, we should see 1; without de-duplication, we'd see 2.
    assert bundle_markers == 1, (
        f"plotly.js banner appears {bundle_markers} times; expected 1 "
        "(bundle should be inlined once and reused)"
    )


def test_plotly_inline_self_contained(tmp_path):
    """Even with the plotly bundle inlined, no HTML *attribute* should
    reference a remote URL. String literals inside the JS bundle (e.g.
    plotly's "Edit on plotly.com" link target) are runtime click
    destinations, not network fetches at load — they don't violate
    self-containment."""
    fig = _make_plotly_fig()
    p = tmp_path / "x.html"
    with Collector(p) as c:
        c.add_figure(fig)
    content = p.read_text()
    # Strip <script>...</script> and <style>...</style> bodies before the
    # attribute check — string literals inside those don't count.
    stripped = re.sub(
        r"<(script|style)\b[^>]*>.*?</\1>",
        lambda m: f"<{m.group(1)}></{m.group(1)}>",
        content,
        flags=re.DOTALL | re.IGNORECASE,
    )
    pattern = re.compile(
        r'(?:src|href|srcset|cite|action|data-src)\s*=\s*["\']https?://',
        re.IGNORECASE,
    )
    assert pattern.search(stripped) is None


def test_plotly_with_matplotlib_in_same_report(tmp_path):
    """matplotlib (raster) and plotly (interactive) figures coexist."""
    plt = pytest.importorskip("matplotlib.pyplot")
    fig_mpl, ax = plt.subplots()
    ax.plot([0, 1])
    fig_plotly = _make_plotly_fig()

    p = tmp_path / "x.html"
    with Collector(p) as c:
        c.add_figure(fig_mpl, title="static")
        c.add_figure(fig_plotly, title="interactive")
    content = p.read_text()
    assert "data:image/png;base64," in content  # matplotlib raster
    assert "rs-figure-plotly" in content  # plotly div
    assert content.count("plotly.js v") == 1


# ---------------------------------------------------------------------------
# Directory mode: bundle written to assets/plotly.min.js once.
# ---------------------------------------------------------------------------

def test_plotly_directory_writes_bundle_to_assets(tmp_path):
    fig = _make_plotly_fig()
    out = tmp_path / "report"
    with Collector(out, mode="directory") as c:
        c.add_figure(fig)
    bundle = out / "assets" / "plotly.min.js"
    assert bundle.exists()
    assert bundle.stat().st_size > 100_000  # plotly.js is several MB

    content = (out / "index.html").read_text()
    # HTML references the bundle via relative URL, not data: or http(s):.
    assert re.search(
        r'<script\b[^>]*\bsrc="assets/plotly\.min\.js"', content
    ) is not None
    # And no inline copy of the bundle.
    assert "plotly.js v" not in content


def test_plotly_directory_bundle_written_once_for_multiple_figs(tmp_path):
    """Multiple plotly figures in directory mode should not re-write the
    bundle. We can't easily check 'wasn't called twice' from the local
    writer, but we can assert exactly one assets/plotly.min.js exists."""
    fig1 = _make_plotly_fig()
    fig2 = _make_plotly_fig()
    out = tmp_path / "report"
    with Collector(out, mode="directory") as c:
        c.add_figure(fig1)
        c.add_figure(fig2)
    bundles = list((out / "assets").glob("plotly*.js"))
    assert len(bundles) == 1


def test_plotly_directory_custom_asset_writer_receives_bundle(tmp_path):
    """A custom AssetWriter sees both the bundle and (none for plotly,
    since plotly figures embed inline JS specs into the HTML) any other
    asset writes."""

    class Recorder:
        def __init__(self):
            self.calls = []

        def write(self, rel: str, content: bytes) -> None:
            self.calls.append((rel, len(content)))

    rec = Recorder()
    fig = _make_plotly_fig()
    with Collector(
        tmp_path / "report", mode="directory", asset_writer=rec
    ) as c:
        c.add_figure(fig)
        c.add_figure(_make_plotly_fig())
    paths = [r for r, _ in rec.calls]
    # One bundle write. Plotly figures don't generate extra asset writes
    # in our design (their per-plot script is inline in the HTML).
    assert paths == ["assets/plotly.min.js"]


# ---------------------------------------------------------------------------
# Friendly error when plotly is not installed.
# ---------------------------------------------------------------------------

def test_plotly_friendly_error_when_missing(tmp_path, monkeypatch):
    class FakePlotlyFig:
        pass

    FakePlotlyFig.__module__ = "plotly.graph_objects"
    FakePlotlyFig.__qualname__ = "Figure"
    fake = FakePlotlyFig()

    monkeypatch.setitem(sys.modules, "plotly", None)
    monkeypatch.setitem(sys.modules, "plotly.io", None)
    monkeypatch.delitem(sys.modules, "runscroll.adapters.plotly", raising=False)

    c = Collector(tmp_path / "x.html")
    with pytest.raises(ImportError) as excinfo:
        c.add_figure(fake)
    assert "plotly" in str(excinfo.value).lower()
    c.save()
