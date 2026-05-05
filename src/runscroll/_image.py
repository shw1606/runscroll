"""Image entry: dispatch + chunked base64 streaming.

Memory contract: for ``bytes`` and path inputs, the transient peak is bounded
by ``_B64_CHUNK`` regardless of source size — base64 is streamed chunk by
chunk. PIL Image and numpy ndarray sources peak at O(payload) because their
libraries don't expose a streaming PNG encoder.

Format detection is by magic bytes (the path's extension is ignored), so the
data URL's MIME stays correct even for mislabeled files.
"""
from __future__ import annotations

import base64
import html as _html
import io
from pathlib import Path
from typing import Any, BinaryIO, Optional, TextIO, Tuple

# 16384 * 3 = 49152: a multiple of 3 keeps b64encode chunks self-contained
# (no padding artifacts at boundaries) while staying small enough that peak
# transient memory is well under 100 KiB per chunk.
_B64_CHUNK = 49152


def _detect_image_format(head: bytes) -> str:
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    if head.startswith(b"BM"):
        return "bmp"
    return "png"  # safe-ish default


def _is_pil_image(obj: Any) -> bool:
    cls = type(obj)
    return cls.__module__.startswith("PIL.") and "Image" in cls.__qualname__


def _is_ndarray(obj: Any) -> bool:
    cls = type(obj)
    return cls.__module__ == "numpy" and cls.__name__ == "ndarray"


def _open_source(source: Any) -> Tuple[BinaryIO, str, Optional[BinaryIO]]:
    """Return (binary_reader, image_format, file_handle_to_close_or_None)."""
    if isinstance(source, bytes):
        return io.BytesIO(source), _detect_image_format(source[:12]), None

    if isinstance(source, (str, Path)):
        path = Path(source)
        f = path.open("rb")
        head = f.read(12)
        f.seek(0)
        return f, _detect_image_format(head), f

    if _is_pil_image(source):
        try:
            from .adapters.pil import pil_to_png_bytes
        except ImportError as e:
            raise ImportError(
                "add_image(PIL.Image) requires Pillow; "
                "install with `pip install runscroll[pil]`"
            ) from e
        return io.BytesIO(pil_to_png_bytes(source)), "png", None

    if _is_ndarray(source):
        try:
            from .adapters.numpy import ndarray_to_png_bytes
        except ImportError as e:
            raise ImportError(
                "add_image(numpy.ndarray) requires numpy and Pillow; "
                "install with `pip install runscroll[pil]` (and numpy)"
            ) from e
        return io.BytesIO(ndarray_to_png_bytes(source)), "png", None

    raise TypeError(
        "add_image: source must be bytes, str/Path, PIL.Image.Image, or "
        f"numpy.ndarray; got {type(source).__name__}"
    )


def _stream_b64(file_obj: TextIO, src: BinaryIO) -> None:
    """Stream-encode src as base64 into file_obj. Peak transient is one chunk."""
    while True:
        chunk = src.read(_B64_CHUNK)
        if not chunk:
            break
        file_obj.write(base64.b64encode(chunk).decode("ascii"))


def write_image(
    file_obj: TextIO,
    source: Any,
    title: str = "",
    caption: str = "",
) -> None:
    """Stream-write an image entry into the open Collector text file."""
    src, fmt, owned = _open_source(source)
    try:
        file_obj.write('<div class="rs-entry rs-image">')
        if title:
            file_obj.write(
                f'<div class="rs-image-title">{_html.escape(title)}</div>'
            )
        alt = _html.escape(caption or title)
        file_obj.write(f'<img alt="{alt}" src="data:image/{fmt};base64,')
        _stream_b64(file_obj, src)
        file_obj.write('">')
        if caption:
            file_obj.write(
                f'<div class="rs-image-caption">{_html.escape(caption)}</div>'
            )
        file_obj.write("</div>\n")
    finally:
        if owned is not None:
            owned.close()


def write_figure_png(
    file_obj: TextIO,
    png_bytes: bytes,
    title: str = "",
    description: str = "",
) -> None:
    """Stream-write a figure entry from already-encoded PNG bytes.

    Used by raster-based figure adapters (matplotlib for now). Plotly's
    interactive embedding goes through a different path (Step 11).
    """
    file_obj.write('<div class="rs-entry rs-figure">')
    if title:
        file_obj.write(
            f'<div class="rs-figure-title">{_html.escape(title)}</div>'
        )
    if description:
        file_obj.write(
            f'<div class="rs-figure-description">{_html.escape(description)}</div>'
        )
    alt = _html.escape(title or "figure")
    file_obj.write(f'<img alt="{alt}" src="data:image/png;base64,')
    _stream_b64(file_obj, io.BytesIO(png_bytes))
    file_obj.write('">')
    file_obj.write("</div>\n")
