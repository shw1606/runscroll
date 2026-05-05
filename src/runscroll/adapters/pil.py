"""PIL.Image adapter — encode to PNG bytes.

The ``from PIL import Image`` at module top is intentional: if Pillow is
not installed, importing this adapter module fails, and the dispatch in
``_image.py`` turns that into a friendly ImportError pointing at the
extras. Without the top-level import, PIL absence wouldn't surface until
the user happened to call a PIL-only method.
"""
from __future__ import annotations

import io
from typing import Any

from PIL import Image as _Image  # noqa: F401  surfaces ImportError on missing Pillow


def pil_to_png_bytes(img: Any) -> bytes:
    """Serialize a PIL.Image.Image to PNG bytes.

    PIL doesn't expose a streaming PNG encoder, so peak memory during this
    call is on the order of the encoded image size. That's the price of
    interoperating with Pillow's API; for huge images, the path-input or
    pre-encoded bytes paths are preferred.
    """
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
