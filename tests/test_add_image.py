"""Tests for Collector.add_image (Step 6).

Covers:
  - bytes / path / PIL.Image / numpy.ndarray dispatch
  - format detection by magic bytes
  - chunked base64 streaming memory safety
  - friendly ImportError when an extras-only adapter is requested without
    its dependency installed
"""
from __future__ import annotations

import base64
import gc
import re
import sys
import tracemalloc

import pytest

from runscroll import Collector

# A minimal but valid PNG (1x1 transparent pixel).
TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c63f8ffff3f000005fe02fea3b13f56000000004945"
    "4e44ae426082"
)

# Minimal JPEG (SOI + APP0 + ... + EOI). We just need the magic prefix
# for format detection — full validity is irrelevant to that test.
JPEG_MAGIC_PREFIX = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00"


def _img_src(html_str: str) -> str:
    """Pull the data URL out of the (single) <img> tag in the rendered HTML."""
    m = re.search(r'<img\b[^>]*\bsrc="([^"]+)"', html_str)
    assert m, f"no <img> tag found in:\n{html_str[:500]}"
    return m.group(1)


# ---------------------------------------------------------------------------
# bytes input
# ---------------------------------------------------------------------------

def test_add_image_bytes_png(tmp_path):
    c = Collector(tmp_path / "x.html")
    c.add_image(TINY_PNG, caption="tiny", title="img1")
    c.save()
    content = (tmp_path / "x.html").read_text()
    src = _img_src(content)
    assert src.startswith("data:image/png;base64,")
    decoded = base64.b64decode(src.split(",", 1)[1])
    assert decoded == TINY_PNG
    assert "rs-image" in content
    assert "tiny" in content
    assert "img1" in content


def test_add_image_bytes_jpeg_format_detected(tmp_path):
    c = Collector(tmp_path / "x.html")
    c.add_image(JPEG_MAGIC_PREFIX)
    c.save()
    content = (tmp_path / "x.html").read_text()
    assert "data:image/jpeg;base64," in content


def test_add_image_bytes_unknown_falls_back_to_png(tmp_path):
    c = Collector(tmp_path / "x.html")
    c.add_image(b"NotARealImage")
    c.save()
    content = (tmp_path / "x.html").read_text()
    # Default fallback is PNG.
    assert "data:image/png;base64," in content


# ---------------------------------------------------------------------------
# path input
# ---------------------------------------------------------------------------

def test_add_image_path_str(tmp_path):
    p = tmp_path / "tiny.png"
    p.write_bytes(TINY_PNG)
    c = Collector(tmp_path / "x.html")
    c.add_image(str(p))
    c.save()
    src = _img_src((tmp_path / "x.html").read_text())
    assert src.startswith("data:image/png;base64,")
    assert base64.b64decode(src.split(",", 1)[1]) == TINY_PNG


def test_add_image_path_pathlib(tmp_path):
    p = tmp_path / "tiny.png"
    p.write_bytes(TINY_PNG)
    c = Collector(tmp_path / "x.html")
    c.add_image(p)
    c.save()
    assert "data:image/png;base64," in (tmp_path / "x.html").read_text()


def test_add_image_path_format_detected_by_magic_not_extension(tmp_path):
    """A PNG mislabeled as .jpg should still emit data:image/png."""
    p = tmp_path / "actually_png.jpg"
    p.write_bytes(TINY_PNG)
    c = Collector(tmp_path / "x.html")
    c.add_image(p)
    c.save()
    assert "data:image/png;base64," in (tmp_path / "x.html").read_text()


# ---------------------------------------------------------------------------
# escaping
# ---------------------------------------------------------------------------

def test_add_image_caption_and_title_escaped(tmp_path):
    c = Collector(tmp_path / "x.html")
    c.add_image(TINY_PNG, caption="<x>caption", title="<y>title")
    c.save()
    content = (tmp_path / "x.html").read_text()
    assert "<x>caption" not in content
    assert "<y>title" not in content
    assert "&lt;x&gt;caption" in content
    assert "&lt;y&gt;title" in content


# ---------------------------------------------------------------------------
# error handling
# ---------------------------------------------------------------------------

def test_add_image_unknown_type_raises(tmp_path):
    c = Collector(tmp_path / "x.html")
    with pytest.raises(TypeError):
        c.add_image(12345)  # type: ignore[arg-type]
    c.save()


# ---------------------------------------------------------------------------
# PIL adapter (skipped when Pillow is not installed)
# ---------------------------------------------------------------------------

def test_add_image_pil(tmp_path):
    Image = pytest.importorskip("PIL.Image")
    img = Image.new("RGB", (8, 8), color=(255, 0, 0))
    c = Collector(tmp_path / "x.html")
    c.add_image(img, caption="red square")
    c.save()
    content = (tmp_path / "x.html").read_text()
    assert "data:image/png;base64," in content
    assert "red square" in content


def test_add_image_pil_friendly_error_when_pillow_missing(
    tmp_path, monkeypatch
):
    """Synthesize a PIL-shaped object and block PIL imports — expect a
    friendly ImportError pointing at the extras."""

    class FakePILImage:
        pass

    FakePILImage.__module__ = "PIL.Image"
    FakePILImage.__qualname__ = "Image"
    fake = FakePILImage()

    # Block PIL and any cached adapter import. Setting sys.modules entries
    # to None makes subsequent ``import`` raise ImportError.
    monkeypatch.setitem(sys.modules, "PIL", None)
    monkeypatch.setitem(sys.modules, "PIL.Image", None)
    monkeypatch.delitem(sys.modules, "runscroll.adapters.pil", raising=False)

    c = Collector(tmp_path / "x.html")
    with pytest.raises(ImportError) as excinfo:
        c.add_image(fake)
    assert "Pillow" in str(excinfo.value) or "pil" in str(excinfo.value).lower()
    c.save()


# ---------------------------------------------------------------------------
# numpy adapter
# ---------------------------------------------------------------------------

def test_add_image_ndarray_grayscale(tmp_path):
    np = pytest.importorskip("numpy")
    pytest.importorskip("PIL")
    arr = np.zeros((8, 8), dtype=np.uint8)
    c = Collector(tmp_path / "x.html")
    c.add_image(arr)
    c.save()
    assert "data:image/png;base64," in (tmp_path / "x.html").read_text()


def test_add_image_ndarray_rgb(tmp_path):
    np = pytest.importorskip("numpy")
    pytest.importorskip("PIL")
    arr = np.zeros((4, 4, 3), dtype=np.uint8)
    arr[..., 0] = 255  # red
    c = Collector(tmp_path / "x.html")
    c.add_image(arr)
    c.save()
    assert "data:image/png;base64," in (tmp_path / "x.html").read_text()


def test_add_image_ndarray_rgba(tmp_path):
    np = pytest.importorskip("numpy")
    pytest.importorskip("PIL")
    arr = np.zeros((4, 4, 4), dtype=np.uint8)
    c = Collector(tmp_path / "x.html")
    c.add_image(arr)
    c.save()
    assert "data:image/png;base64," in (tmp_path / "x.html").read_text()


def test_add_image_ndarray_float_normalized(tmp_path):
    np = pytest.importorskip("numpy")
    pytest.importorskip("PIL")
    # Floats in 0..1 should be normalized to 0..255.
    arr = np.linspace(0.0, 1.0, 64, dtype=np.float32).reshape(8, 8)
    c = Collector(tmp_path / "x.html")
    c.add_image(arr)
    c.save()
    assert "data:image/png;base64," in (tmp_path / "x.html").read_text()


def test_add_image_ndarray_invalid_shape_raises(tmp_path):
    np = pytest.importorskip("numpy")
    pytest.importorskip("PIL")
    arr = np.zeros((4, 4, 5), dtype=np.uint8)
    c = Collector(tmp_path / "x.html")
    with pytest.raises(ValueError):
        c.add_image(arr)
    c.save()


# ---------------------------------------------------------------------------
# Memory safety: large path-input must NOT pin the full image in memory.
# ---------------------------------------------------------------------------

def test_add_image_path_large_streams_chunked(tmp_path):
    """Streaming contract: encoding a 30 MiB on-disk binary must not
    leave the full payload resident after add_image returns."""
    # Build a fake "image" file. The bytes don't have to be a real image —
    # the streaming code reads bytes and base64-encodes them; format
    # detection peeks first 12 bytes only.
    payload_bytes = 30 * 1024 * 1024
    p = tmp_path / "big.bin"
    with p.open("wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")  # PNG magic so format detects as png
        # Pad with arbitrary bytes; chunk write to avoid building one giant
        # bytes object on the test side.
        chunk = b"\x00" * (1024 * 1024)
        remaining = payload_bytes - 8
        while remaining > 0:
            n = min(len(chunk), remaining)
            f.write(chunk[:n])
            remaining -= n

    c = Collector(tmp_path / "x.html")

    gc.collect()
    tracemalloc.start()
    try:
        baseline = tracemalloc.get_traced_memory()[0]
        c.add_image(p)
        gc.collect()
        after = tracemalloc.get_traced_memory()[0]
    finally:
        tracemalloc.stop()
    c.save()

    growth = after - baseline
    # The file is 30 MiB on disk. If we were buffering the full image
    # in memory, growth would be at least 30 MiB. We allow up to 1 MiB
    # transient (well above the 49152 chunk size and any file buffering).
    assert growth < 1 * 1024 * 1024, (
        f"30 MiB on-disk image left {growth/1024/1024:.2f} MiB resident; "
        "base64 streaming is broken"
    )
    # And the rendered HTML should be ~ 4/3 * 30 MiB plus framing.
    rendered_size = (tmp_path / "x.html").stat().st_size
    assert rendered_size >= int(payload_bytes * 1.33)
