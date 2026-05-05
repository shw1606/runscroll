"""Streaming append-write Collector.

The single most important architectural decision (handoff §5):
**no in-memory entry buffer.** Each ``add_*`` call serializes its content to
the output file and flushes immediately. The Python-side state is just
counters, a section depth counter, and a file handle — a few KB regardless
of report size.
"""
from __future__ import annotations

import html
import traceback
from pathlib import Path
from types import TracebackType
from typing import Any, Literal, Mapping, Optional, Sequence, Type, Union

from ._image import (
    write_figure_png_directory,
    write_figure_png_inline,
    write_image_directory,
    write_image_inline,
)
from ._render import render_footer, render_header
from .asset_writer import AssetWriter, LocalAssetWriter
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
        mode: Literal["inline", "directory"] = "inline",
        asset_writer: Optional[AssetWriter] = None,
        log_exceptions: bool = True,
    ) -> None:
        if mode not in ("inline", "directory"):
            raise ValueError(
                f"mode must be 'inline' or 'directory', got {mode!r}"
            )
        self.path = Path(path)
        self.title = title
        self.mode = mode
        self._log_exceptions = log_exceptions
        self._asset_writer: Optional[AssetWriter]
        if mode == "inline":
            if asset_writer is not None:
                raise ValueError(
                    "asset_writer is only meaningful in directory mode"
                )
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._html_path = self.path
            self._asset_writer = None
        else:  # directory
            self.path.mkdir(parents=True, exist_ok=True)
            self._html_path = self.path / "index.html"
            self._asset_writer = asset_writer or LocalAssetWriter(self.path)
        self._file = self._html_path.open("w", encoding="utf-8")
        self._closed = False
        self._entry_count = 0
        self._section_depth = 0
        self._section_seq = 0
        self._asset_seq = 0
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

    def add_image(
        self,
        source: Any,
        caption: str = "",
        title: str = "",
    ) -> None:
        """Append an image entry. ``source`` can be bytes, a file path,
        a PIL Image, or a numpy ndarray.

        In inline mode, base64 is streamed chunk-by-chunk into the HTML.
        In directory mode, asset bytes are handed to the AssetWriter and
        the HTML embeds a relative URL.
        """
        self._check_open()
        if self.mode == "inline":
            write_image_inline(self._file, source, title=title, caption=caption)
        else:
            self._asset_seq += 1
            write_image_directory(
                self._file,
                source,
                self._asset_writer,
                self._asset_seq,
                title=title,
                caption=caption,
            )
        self._file.flush()
        self._entry_count += 1

    def add_figure(
        self,
        fig: Any,
        title: str = "",
        description: str = "",
        close: bool = True,
    ) -> None:
        """Append a figure entry.

        Currently supports matplotlib Figures. Plotly and Bokeh are added
        in later steps. ``close=True`` (default) releases the figure's
        resources after encoding — the moulder pipeline that seeded
        runscroll consistently followed every save with ``plt.close(fig)``,
        so we absorb that pattern.
        """
        self._check_open()
        cls = type(fig)
        if cls.__module__.startswith("matplotlib."):
            try:
                from .adapters.matplotlib import close_figure, fig_to_png_bytes
            except ImportError as e:
                raise ImportError(
                    "add_figure(matplotlib Figure) requires matplotlib; "
                    "install with `pip install runscroll[matplotlib]`"
                ) from e
            png = fig_to_png_bytes(fig)
            if close:
                close_figure(fig)
            if self.mode == "inline":
                write_figure_png_inline(
                    self._file, png, title=title, description=description
                )
            else:
                self._asset_seq += 1
                write_figure_png_directory(
                    self._file,
                    png,
                    self._asset_writer,
                    self._asset_seq,
                    title=title,
                    description=description,
                )
            del png  # release the PNG bytes promptly
        else:
            raise TypeError(
                "add_figure: fig must be a matplotlib Figure (plotly/bokeh "
                f"come in later steps); got {type(fig).__name__}"
            )
        self._file.flush()
        self._entry_count += 1

    # ------------------------------------------------------------------
    # Sections
    # ------------------------------------------------------------------

    def section(self, name: str) -> "SectionContext":
        """Return a context manager opening a (possibly nested) section."""
        self._check_open()
        return SectionContext(self, name)

    def _open_section(self, name: str) -> None:
        self._check_open()
        self._section_depth += 1
        self._section_seq += 1
        section_id = self._section_seq
        safe = html.escape(name)
        # h-level: nested sections clamp at h6 to stay valid HTML.
        h_level = min(self._section_depth + 1, 6)
        self._file.write(
            f'<section class="rs-section" data-rs-section-id="{section_id}" '
            f'data-rs-section-name="{safe}" data-rs-depth="{self._section_depth}" '
            f'id="rs-section-{section_id}">'
            f'<header class="rs-section-header">'
            f'<h{h_level} class="rs-section-title">{safe}</h{h_level}>'
            f"</header>"
            f'<div class="rs-section-body">\n'
        )
        self._file.flush()

    def _close_section(self) -> None:
        if self._section_depth <= 0:
            return
        self._file.write("</div></section>\n")
        self._file.flush()
        self._section_depth -= 1

    # ------------------------------------------------------------------
    # Context manager + finalize
    # ------------------------------------------------------------------

    def __enter__(self) -> "Collector":
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> Literal[False]:
        # If the user-provided block raised, optionally log it as an error
        # entry before closing — best-effort, never re-raises.
        if exc_type is not None and not self._closed and self._log_exceptions:
            try:
                tb_str = "".join(traceback.format_exception(exc_type, exc_val, tb))
                self.add_text(tb_str, level="error")
            except Exception:
                pass
        # Close any sections the user opened but didn't close.
        while self._section_depth > 0:
            try:
                self._close_section()
            except Exception:
                break
        try:
            self.save()
        except Exception:
            pass
        return False  # never swallow

    def save(self) -> str:
        """Write the closing tags, close the file, return the final path."""
        if self._closed:
            return str(self.path)
        self._write_footer()
        self._file.close()
        self._closed = True
        return str(self.path)

    def __del__(self) -> None:
        # Best-effort cleanup. Users should call save() or use the Collector
        # as a context manager.
        f = getattr(self, "_file", None)
        if f is not None and not getattr(self, "_closed", True):
            try:
                if not f.closed:
                    f.close()
            except Exception:
                pass


class SectionContext:
    """Context manager returned by ``Collector.section(name)``.

    Sections are opened/closed via the Collector so the file always sees
    matched ``<section>`` tags, even when user code raises inside the block —
    the Collector's ``__exit__`` walks any unclosed sections shut.
    """

    __slots__ = ("_collector", "name")

    def __init__(self, collector: "Collector", name: str) -> None:
        self._collector = collector
        self.name = name

    def __enter__(self) -> "SectionContext":
        self._collector._open_section(self.name)
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> Literal[False]:
        self._collector._close_section()
        return False  # never swallow
