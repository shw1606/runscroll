"""Streaming append-write Collector.

The single most important architectural decision (handoff §5):
**no in-memory entry buffer.** Each ``add_*`` call serializes its content to
the output file and flushes immediately. The Python-side state is just
counters and a file handle — a few KB regardless of report size.
"""
from __future__ import annotations

import html
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence, Union

from ._render import render_footer, render_header
from .entries import render_code, render_kv, render_table

TextLevel = Literal["info", "debug", "warning", "error", "success"]

_VALID_LEVELS = frozenset(("info", "debug", "warning", "error", "success"))


class Collector:
    """Build a single self-contained HTML report by streaming entries to disk.

    The output file is opened in ``__init__`` and the HTML header is written
    immediately. Each ``add_*`` call appends serialized HTML and flushes; the
    in-Python representation of that entry is then released. Call ``save()``
    when done — it writes the closing tags and closes the file.
    """

    def __init__(
        self,
        path: Union[str, Path],
        title: str = "Run report",
    ) -> None:
        self.path = Path(path)
        self.title = title
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.path.open("w", encoding="utf-8")
        self._closed = False
        self._entry_count = 0
        self._write_header()

    def _write_header(self) -> None:
        self._file.write(render_header(self.title))
        self._file.flush()

    def _write_footer(self) -> None:
        self._file.write(render_footer())
        self._file.flush()

    def _check_open(self) -> None:
        if self._closed:
            raise RuntimeError(
                "Collector is already saved/closed; cannot add more entries"
            )

    def add_text(self, text: str, level: TextLevel = "info") -> None:
        """Append a text log entry. Serialized and flushed immediately."""
        self._check_open()
        if level not in _VALID_LEVELS:
            raise ValueError(
                f"level must be one of {sorted(_VALID_LEVELS)}, got {level!r}"
            )
        safe = html.escape(str(text))
        self._file.write(
            f'<div class="rs-entry rs-text rs-text-{level}">{safe}</div>\n'
        )
        self._file.flush()
        self._entry_count += 1

    def add_kv(self, mapping: Mapping[str, Any], title: str = "") -> None:
        """Append a two-column key/value table."""
        self._check_open()
        self._file.write(render_kv(mapping, title=title))
        self._file.flush()
        self._entry_count += 1

    def add_code(self, code: str, lang: str = "", title: str = "") -> None:
        """Append a code block. ``lang`` is recorded as ``data-rs-lang`` for
        future syntax-highlighting hooks; no highlighting is applied here."""
        self._check_open()
        self._file.write(render_code(code, lang=lang, title=title))
        self._file.flush()
        self._entry_count += 1

    def add_table(self, data: Sequence[Any], title: str = "") -> None:
        """Append a tabular entry from a list of dicts or list of lists.

        pandas DataFrame support is provided by the pandas adapter
        (separate optional dependency); this stdlib path covers the
        common log-friendly shapes."""
        self._check_open()
        self._file.write(render_table(data, title=title))
        self._file.flush()
        self._entry_count += 1

    def save(self) -> str:
        """Write the closing tags, close the file, return the final path."""
        if self._closed:
            return str(self.path)
        self._write_footer()
        self._file.close()
        self._closed = True
        return str(self.path)

    def __del__(self) -> None:
        # Best-effort cleanup. Users should call save() or (from Step 8) use
        # the Collector as a context manager.
        f = getattr(self, "_file", None)
        if f is not None and not getattr(self, "_closed", True):
            try:
                if not f.closed:
                    f.close()
            except Exception:
                pass
