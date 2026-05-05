"""Tests for Collector.add_figure (Step 7) — matplotlib only.

Plotly / Bokeh come in a later step.
"""
from __future__ import annotations

import re
import sys

import pytest

from runscroll import Collector


def test_add_figure_matplotlib_basic(tmp_path):
    plt = pytest.importorskip("matplotlib.pyplot")
    fig, ax = plt.subplots()
    ax.plot([1, 2, 3], [1, 4, 9])
    ax.set_title("y = x^2")

    c = Collector(tmp_path / "x.html")
    c.add_figure(fig, title="parabola", description="example fit")
    c.save()

    content = (tmp_path / "x.html").read_text()
    assert "rs-figure" in content
    assert "parabola" in content
    assert "example fit" in content
    assert "data:image/png;base64," in content


def test_add_figure_default_close_releases_figure(tmp_path):
    """close=True (default) calls plt.close(fig). After the call, the figure
    should no longer be tracked by pyplot."""
    plt = pytest.importorskip("matplotlib.pyplot")
    fig, ax = plt.subplots()
    ax.plot([0, 1])
    fignum = fig.number

    assert plt.fignum_exists(fignum)
    c = Collector(tmp_path / "x.html")
    c.add_figure(fig)
    c.save()
    assert not plt.fignum_exists(fignum)


def test_add_figure_close_false_keeps_figure(tmp_path):
    plt = pytest.importorskip("matplotlib.pyplot")
    fig, ax = plt.subplots()
    ax.plot([0, 1])
    fignum = fig.number

    c = Collector(tmp_path / "x.html")
    c.add_figure(fig, close=False)
    c.save()
    assert plt.fignum_exists(fignum)
    plt.close(fig)


def test_add_figure_unknown_type_raises(tmp_path):
    c = Collector(tmp_path / "x.html")
    with pytest.raises(TypeError):
        c.add_figure(object())  # not a matplotlib Figure
    c.save()


def test_add_figure_title_and_description_escaped(tmp_path):
    plt = pytest.importorskip("matplotlib.pyplot")
    fig, ax = plt.subplots()
    ax.plot([0, 1])

    c = Collector(tmp_path / "x.html")
    c.add_figure(fig, title="<x>title", description="<y>desc")
    c.save()

    content = (tmp_path / "x.html").read_text()
    assert "<x>title" not in content
    assert "<y>desc" not in content
    assert "&lt;x&gt;title" in content
    assert "&lt;y&gt;desc" in content


def test_add_figure_friendly_error_when_matplotlib_missing(tmp_path, monkeypatch):
    """Synthesize a matplotlib-shaped object and block the matplotlib import.
    Expect a friendly ImportError pointing at the extras."""

    class FakeFigure:
        pass

    FakeFigure.__module__ = "matplotlib.figure"
    FakeFigure.__qualname__ = "Figure"
    fake = FakeFigure()

    monkeypatch.setitem(sys.modules, "matplotlib", None)
    monkeypatch.delitem(sys.modules, "runscroll.adapters.matplotlib", raising=False)

    c = Collector(tmp_path / "x.html")
    with pytest.raises(ImportError) as excinfo:
        c.add_figure(fake)
    assert "matplotlib" in str(excinfo.value)
    c.save()


def test_add_figure_routes_through_rs_figure_entry(tmp_path):
    """Verify the figure entry uses .rs-figure (not .rs-image), so JS/CSS
    can target figures distinctly from raw images."""
    plt = pytest.importorskip("matplotlib.pyplot")
    fig, ax = plt.subplots()
    ax.plot([0, 1])

    c = Collector(tmp_path / "x.html")
    c.add_figure(fig, title="t")
    c.save()

    content = (tmp_path / "x.html").read_text()
    figure_blocks = re.findall(r'class="[^"]*rs-figure\b[^"]*"', content)
    assert figure_blocks, "expected at least one rs-figure entry"
