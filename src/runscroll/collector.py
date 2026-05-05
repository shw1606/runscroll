"""Streaming append-write Collector.

The single most important architectural decision (handoff §5):
**no in-memory entry buffer.** Each ``add_*`` call serializes its content to
the output file and flushes immediately. The Python-side state is just
counters and a file handle — a few KB regardless of report size.
"""
from __future__ import annotations

import html
from pathlib import Path
from typing import Literal, Union

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
        title_safe = html.escape(self.title)
        self._file.write(
            "<!DOCTYPE html>\n"
            '<html lang="en">\n'
            "<head>\n"
            '<meta charset="UTF-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
            f"<title>{title_safe}</title>\n"
            "</head>\n"
            "<body>\n"
            '<header class="rs-header">\n'
            f"<h1>{title_safe}</h1>\n"
            "</header>\n"
            '<main class="rs-content">\n'
        )
        self._file.flush()

    def _write_footer(self) -> None:
        self._file.write("</main>\n</body>\n</html>\n")
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
