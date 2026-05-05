"""numpy ndarray adapter — convert to PIL.Image then to PNG bytes.

Handoff §8.4 shape/dtype rules:
  shape (H, W)        -> grayscale ('L')
  shape (H, W, 3)     -> RGB
  shape (H, W, 4)     -> RGBA
  dtype uint8         -> used as-is
  floating dtype      -> normalized to 0..255 (min->0, max->255) then cast
"""
from __future__ import annotations

import io
from typing import Any

import numpy as np


def ndarray_to_png_bytes(arr: Any) -> bytes:
    from PIL import Image  # raises ImportError if Pillow not installed

    a = np.asarray(arr)

    if a.dtype != np.uint8:
        if np.issubdtype(a.dtype, np.floating):
            if a.size > 0:
                mn = float(a.min())
                mx = float(a.max())
                if mx > mn:
                    a = (a - mn) * (255.0 / (mx - mn))
                else:
                    a = np.zeros_like(a)
        a = np.clip(a, 0, 255).astype(np.uint8)

    if a.ndim == 2:
        mode = "L"
    elif a.ndim == 3 and a.shape[2] == 3:
        mode = "RGB"
    elif a.ndim == 3 and a.shape[2] == 4:
        mode = "RGBA"
    else:
        raise ValueError(
            "add_image: ndarray must be (H, W), (H, W, 3), or (H, W, 4); "
            f"got shape {a.shape}"
        )

    img = Image.fromarray(a, mode=mode)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
