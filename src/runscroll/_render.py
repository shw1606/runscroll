"""Template + static asset loading for inline-mode rendering.

Templates use plain ``__RUNSCROLL_<NAME>__`` sentinel tokens, replaced via
``str.replace``. We intentionally avoid ``str.format`` and ``Template`` so
that CSS/JS payloads (which contain ``{`` and ``}``) need no escaping.

Loaded resources are cached per process — a typical Collector instantiation
hits cold cache, but subsequent ones in the same process reuse the read.
"""
from __future__ import annotations

import html
from datetime import datetime
from functools import lru_cache
from importlib import resources


@lru_cache(maxsize=8)
def _read_resource(package: str, name: str) -> str:
    return resources.files(package).joinpath(name).read_text(encoding="utf-8")


def _template(name: str) -> str:
    return _read_resource("runscroll.templates", name)


def _static(name: str) -> str:
    return _read_resource("runscroll.static", name)


def render_header(title: str) -> str:
    """Return the document header with CSS inlined and title escaped."""
    css = _static("runscroll.css")
    safe_title = html.escape(title)
    generated = html.escape(datetime.now().isoformat(timespec="seconds"))
    return (
        _template("header.html")
        .replace("__RUNSCROLL_CSS__", css)
        .replace("__RUNSCROLL_TITLE__", safe_title)
        .replace(
            'data-rs-meta="generated"></div>',
            f'data-rs-meta="generated">Generated {generated}</div>',
        )
    )


def render_footer() -> str:
    """Return the document footer with JS inlined."""
    js = _static("runscroll.js")
    return _template("footer.html").replace("__RUNSCROLL_JS__", js)
