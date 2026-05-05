"""Tests for directory mode + AssetWriter (Step 10)."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from runscroll import AssetWriter, Collector, LocalAssetWriter

TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c63f8ffff3f000005fe02fea3b13f56000000004945"
    "4e44ae426082"
)


# ---------------------------------------------------------------------------
# Basic shape: directory mode emits index.html + assets/
# ---------------------------------------------------------------------------

def test_directory_mode_emits_index_and_assets(tmp_path):
    out = tmp_path / "report"
    with Collector(out, mode="directory", title="dir mode") as c:
        c.add_text("hello")
        c.add_image(TINY_PNG)
    assert out.is_dir()
    assert (out / "index.html").exists()
    assert (out / "assets").is_dir()
    # One asset for the image.
    assets = sorted((out / "assets").iterdir())
    assert len(assets) == 1
    assert assets[0].name == "0001.png"
    assert assets[0].read_bytes() == TINY_PNG


def test_directory_mode_html_uses_relative_asset_url(tmp_path):
    out = tmp_path / "report"
    with Collector(out, mode="directory") as c:
        c.add_image(TINY_PNG)
    content = (out / "index.html").read_text()
    # No data: URL — only relative.
    assert "data:image/" not in content
    assert re.search(r'<img[^>]*src="assets/0001\.png"', content)


def test_directory_mode_save_returns_directory_path(tmp_path):
    out = tmp_path / "report"
    c = Collector(out, mode="directory")
    c.add_text("x")
    final = c.save()
    assert Path(final) == out


def test_directory_mode_serves_static_when_opened(tmp_path):
    """Self-containment for directory mode: opening index.html with the
    `assets/` sibling present must show all assets via relative paths
    only — no http(s):// or data: scheme."""
    out = tmp_path / "report"
    with Collector(out, mode="directory") as c:
        c.add_image(TINY_PNG, title="t")
    content = (out / "index.html").read_text()
    assert "http://" not in content
    assert "https://" not in content
    # CSS/JS still inlined (only assets get externalized).
    assert "<style>" in content
    assert "<script>" in content


# ---------------------------------------------------------------------------
# Asset numbering increments across all add_* that produce assets.
# ---------------------------------------------------------------------------

def test_directory_mode_asset_seq_increments_across_images(tmp_path):
    out = tmp_path / "report"
    with Collector(out, mode="directory") as c:
        c.add_image(TINY_PNG)
        c.add_image(TINY_PNG)
        c.add_image(TINY_PNG)
    assets = sorted((out / "assets").iterdir())
    assert [a.name for a in assets] == ["0001.png", "0002.png", "0003.png"]


def test_directory_mode_figure_writes_asset(tmp_path):
    plt = pytest.importorskip("matplotlib.pyplot")
    fig, ax = plt.subplots()
    ax.plot([0, 1, 2])
    out = tmp_path / "report"
    with Collector(out, mode="directory") as c:
        c.add_figure(fig, title="t")
    assets = sorted((out / "assets").iterdir())
    assert len(assets) == 1
    assert assets[0].suffix == ".png"


def test_directory_mode_mixed_images_and_figures_share_seq(tmp_path):
    plt = pytest.importorskip("matplotlib.pyplot")
    fig, ax = plt.subplots()
    ax.plot([0, 1])
    out = tmp_path / "report"
    with Collector(out, mode="directory") as c:
        c.add_image(TINY_PNG)
        c.add_figure(fig)
        c.add_image(TINY_PNG)
    assets = sorted((out / "assets").iterdir())
    assert [a.name for a in assets] == ["0001.png", "0002.png", "0003.png"]


# ---------------------------------------------------------------------------
# Same Collector code works in both modes (API parity).
# ---------------------------------------------------------------------------

def test_same_user_code_works_in_both_modes(tmp_path):
    """Build the same content twice with different modes."""
    plt = pytest.importorskip("matplotlib.pyplot")

    def build(c):
        c.add_text("hi")
        c.add_kv({"a": 1})
        c.add_code("x=1", lang="python")
        c.add_table([{"col": 1}])
        c.add_image(TINY_PNG)
        fig, ax = plt.subplots()
        ax.plot([0, 1])
        c.add_figure(fig)
        with c.section("S"):
            c.add_text("inside")

    inline_path = tmp_path / "inline.html"
    with Collector(inline_path, mode="inline") as c:
        build(c)

    dir_path = tmp_path / "dir"
    with Collector(dir_path, mode="directory") as c:
        build(c)

    inline_html = inline_path.read_text()
    dir_html = (dir_path / "index.html").read_text()

    # Both have a section.
    for h in (inline_html, dir_html):
        assert "<section" in h
        assert "rs-text" in h and "rs-kv" in h and "rs-code" in h
        assert "rs-image" in h and "rs-figure" in h

    # Inline embeds data URLs; directory uses relative paths.
    assert "data:image/png;base64," in inline_html
    assert "data:image/png;base64," not in dir_html
    assert (dir_path / "assets" / "0001.png").exists()
    assert (dir_path / "assets" / "0002.png").exists()


# ---------------------------------------------------------------------------
# AssetWriter Protocol: custom implementation gets called.
# ---------------------------------------------------------------------------

class _RecordingAssetWriter:
    def __init__(self):
        self.calls: list[tuple[str, bytes]] = []

    def write(self, relative_path: str, content: bytes) -> None:
        self.calls.append((relative_path, content))


def test_custom_asset_writer_used_for_assets(tmp_path):
    rec = _RecordingAssetWriter()
    out = tmp_path / "report"
    with Collector(out, mode="directory", asset_writer=rec) as c:
        c.add_image(TINY_PNG)
        c.add_image(b"\xff\xd8\xff" + b"\x00" * 32)  # JPEG magic
    assert len(rec.calls) == 2
    paths = [c[0] for c in rec.calls]
    assert paths == ["assets/0001.png", "assets/0002.jpeg"]
    # Local index.html still written to the output directory.
    assert (out / "index.html").exists()


def test_custom_asset_writer_does_not_create_local_assets(tmp_path):
    """When a custom AssetWriter is supplied, the local assets/ folder
    should NOT be auto-populated by us — the custom writer owns that."""
    rec = _RecordingAssetWriter()
    out = tmp_path / "report"
    with Collector(out, mode="directory", asset_writer=rec) as c:
        c.add_image(TINY_PNG)
    # Index file is local, but no assets/ since custom writer never touched
    # the local disk.
    assert (out / "index.html").exists()
    assert not (out / "assets").exists()


def test_asset_writer_protocol_runtime_check():
    """AssetWriter is runtime_checkable, so isinstance() should work
    against an unrelated class that satisfies the .write signature."""
    rec = _RecordingAssetWriter()
    assert isinstance(rec, AssetWriter)


# ---------------------------------------------------------------------------
# LocalAssetWriter.write_from_path fast path (path source, no in-memory copy)
# ---------------------------------------------------------------------------

def test_local_asset_writer_streams_path_input(tmp_path):
    """For a path-source image with the default LocalAssetWriter, the
    Collector should use write_from_path (shutil.copyfile) — that means
    the bytes never round-trip through Python."""
    src_image = tmp_path / "input.png"
    src_image.write_bytes(TINY_PNG)
    out = tmp_path / "report"
    with Collector(out, mode="directory") as c:
        c.add_image(src_image)
    copied = out / "assets" / "0001.png"
    assert copied.read_bytes() == TINY_PNG


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def test_invalid_mode_raises():
    with pytest.raises(ValueError, match="mode"):
        Collector("/tmp/x", mode="zip")  # type: ignore[arg-type]


def test_asset_writer_rejected_in_inline_mode(tmp_path):
    rec = _RecordingAssetWriter()
    with pytest.raises(ValueError, match="asset_writer"):
        Collector(tmp_path / "x.html", mode="inline", asset_writer=rec)
