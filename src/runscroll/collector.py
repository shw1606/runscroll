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
    when done — or use the Collector as a context manager (recommended), in
    which case ``__exit__`` saves automatically and logs any exception.

    Example:
        >>> from runscroll import Collector
        >>> with Collector("report.html", title="Daily ETL") as report:
        ...     report.add_kv({"started_at": "2026-05-05T09:00"})
        ...     with report.section("Extract"):
        ...         report.add_text("loaded 1,234,567 rows")
        ...     report.add_text("done", level="success")
    """

    def __init__(
        self,
        path: Union[str, Path],
        title: str = "Run report",
        mode: Literal["inline", "directory"] = "inline",
        asset_writer: Optional[AssetWriter] = None,
        log_exceptions: bool = True,
    ) -> None:
        """Open the output file and write the HTML header.

        Args:
            path: For ``mode="inline"``, the destination ``.html`` file.
                For ``mode="directory"``, the destination directory; the
                HTML lands at ``<path>/index.html`` and assets at
                ``<path>/assets/``.
            title: Shown in the document ``<title>`` and as the ``<h1>``.
            mode: ``"inline"`` (default) embeds all assets as base64
                data URLs in one file. ``"directory"`` writes assets as
                separate files referenced via relative URLs.
            asset_writer: Optional ``AssetWriter`` for ``directory`` mode
                only — plug in S3 / GCS / etc. by implementing
                ``write(rel_path, bytes)``. If omitted, a
                ``LocalAssetWriter`` writing under ``path`` is used.
            log_exceptions: When the Collector is used as a context
                manager and the ``with`` block raises, log the traceback
                as an error-level text entry before saving. Default True.

        Example:
            >>> from runscroll import Collector
            >>> with Collector("out.html", title="My run") as report:
            ...     report.add_text("hello")
        """
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
        self._plotly_bundle_emitted = False
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
        """Append a text log entry, color-coded by level.

        Args:
            text: The text to record. HTML-escaped automatically.
            level: One of ``"info"``, ``"debug"``, ``"warning"``,
                ``"error"``, ``"success"``. Drives the color and the
                level-filter chip in the rendered report.

        Example:
            >>> report.add_text("starting batch")
            >>> report.add_text("3 rows dropped", level="warning")
            >>> report.add_text("done", level="success")
        """
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
        """Append a two-column key/value block. Ideal for run config,
        hyperparameters, or summary stats.

        Args:
            mapping: The dict to render. Insertion order preserved.
                Values are stringified via ``str()`` and HTML-escaped.
            title: Optional heading shown above the kv block.

        Example:
            >>> report.add_kv(
            ...     {"model": "resnet50", "lr": 3e-4, "bs": 64},
            ...     title="Hyperparameters",
            ... )
        """
        self._check_open()
        self._file.write(render_kv(mapping, title=title))
        self._file.flush()
        self._entry_count += 1

    def add_code(self, code: str, lang: str = "", title: str = "") -> None:
        """Append a preformatted code block.

        Args:
            code: The code to render. HTML-escaped; whitespace preserved.
            lang: Recorded as ``data-rs-lang`` on the ``<pre>`` for
                future syntax-highlighting hooks; no highlighting is
                applied here.
            title: Optional heading shown above the block.

        Example:
            >>> report.add_code(
            ...     "SELECT count(*) FROM events WHERE day = '2026-05-05'",
            ...     lang="sql",
            ...     title="Validation query",
            ... )
        """
        self._check_open()
        self._file.write(render_code(code, lang=lang, title=title))
        self._file.flush()
        self._entry_count += 1

    def add_table(self, data: Sequence[Any], title: str = "") -> None:
        """Append a tabular entry from a ``list[dict]`` or ``list[list]``.

        Args:
            data: ``list[dict]`` — column union of all keys, insertion
                order preserved, missing keys render as empty cells.
                ``list[list]`` or ``list[tuple]`` — rendered without a
                ``<thead>``; ragged rows allowed.
            title: Optional heading shown above the table.

        Example:
            >>> report.add_table(
            ...     [{"class": "cat", "precision": 0.91, "recall": 0.88},
            ...      {"class": "dog", "precision": 0.94, "recall": 0.92}],
            ...     title="Per-class metrics",
            ... )

        Note:
            pandas DataFrames are not auto-converted here. Pass
            ``df.to_dict("records")`` for a list-of-dicts rendering.
        """
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
        """Append an image entry.

        Args:
            source: One of:
                - ``bytes`` — already-encoded image bytes (PNG/JPEG/GIF/
                  WebP/BMP auto-detected by magic bytes).
                - ``str`` or ``Path`` — file path. Streamed from disk so
                  large files don't load into memory.
                - ``PIL.Image.Image`` — encoded to PNG bytes.
                  Requires ``pip install runscroll[pil]``.
                - ``numpy.ndarray`` — shape ``(H, W)`` / ``(H, W, 3)`` /
                  ``(H, W, 4)``. ``float`` dtype is min-max normalized.
                  Requires ``pip install runscroll[pil]``.
            caption: Shown below the image. HTML-escaped.
            title: Optional heading shown above the image. HTML-escaped.

        In inline mode, base64 is streamed chunk-by-chunk into the HTML
        — peak memory stays bounded regardless of image size. In
        directory mode, the asset is handed to the ``AssetWriter`` and
        the HTML embeds a relative URL.

        Example:
            >>> # bytes (no extras needed)
            >>> with open("plot.png", "rb") as f:
            ...     report.add_image(f.read(), caption="my plot")
            >>> # path (best for large files — streamed)
            >>> report.add_image("/tmp/big_image.png")
            >>> # PIL
            >>> from PIL import Image
            >>> report.add_image(Image.new("RGB", (8, 8), "red"))
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
        """Append a figure entry. Supports matplotlib and plotly Figures.

        Args:
            fig: A ``matplotlib.figure.Figure`` (rendered as an inline
                PNG) or a ``plotly.graph_objects.Figure`` (rendered as
                an interactive ``<div>`` with the plotly.js bundle
                inlined exactly once per Collector).
            title: Optional heading shown above the figure.
            description: Optional caption shown below the title.
            close: For matplotlib only. Calls ``plt.close(fig)`` after
                encoding so pyplot's figure registry doesn't grow.
                Default True (matches the convention seeding pipelines
                established).

        Requires the matching extra: ``pip install runscroll[matplotlib]``
        or ``pip install runscroll[plotly]``.

        Example:
            >>> import matplotlib.pyplot as plt
            >>> fig, ax = plt.subplots()
            >>> ax.plot([1, 2, 3], [1, 4, 9])
            >>> report.add_figure(fig, title="y = x^2")
            >>> # Plotly works the same way:
            >>> import plotly.graph_objects as go
            >>> pf = go.Figure(go.Scatter(x=[1, 2, 3], y=[1, 4, 9]))
            >>> report.add_figure(pf, title="interactive y = x^2")
        """
        self._check_open()
        cls = type(fig)
        if cls.__module__.startswith("matplotlib."):
            self._add_matplotlib_figure(
                fig, title=title, description=description, close=close
            )
        elif cls.__module__.startswith("plotly."):
            self._add_plotly_figure(fig, title=title, description=description)
        else:
            raise TypeError(
                "add_figure: fig must be a matplotlib Figure or a plotly "
                f"Figure (bokeh planned for later); got {type(fig).__name__}"
            )
        self._file.flush()
        self._entry_count += 1

    def _add_matplotlib_figure(
        self, fig: Any, title: str, description: str, close: bool
    ) -> None:
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
        del png

    def _add_plotly_figure(
        self, fig: Any, title: str, description: str
    ) -> None:
        try:
            from .adapters.plotly import (
                figure_to_html_div_only,
                figure_to_html_with_inline_bundle,
                get_plotlyjs_bundle,
            )
        except ImportError as e:
            raise ImportError(
                "add_figure(plotly Figure) requires plotly; "
                "install with `pip install runscroll[plotly]`"
            ) from e

        # Open the figure block.
        self._file.write('<div class="rs-entry rs-figure rs-figure-plotly">')
        if title:
            self._file.write(
                f'<div class="rs-figure-title">{html.escape(title)}</div>'
            )
        if description:
            self._file.write(
                f'<div class="rs-figure-description">{html.escape(description)}</div>'
            )

        if self.mode == "inline":
            if not self._plotly_bundle_emitted:
                self._file.write(figure_to_html_with_inline_bundle(fig))
                self._plotly_bundle_emitted = True
            else:
                self._file.write(figure_to_html_div_only(fig))
        else:  # directory
            if not self._plotly_bundle_emitted:
                bundle = get_plotlyjs_bundle()
                self._asset_writer.write(
                    "assets/plotly.min.js", bundle.encode("utf-8")
                )
                self._file.write(
                    '<script src="assets/plotly.min.js"></script>'
                )
                self._plotly_bundle_emitted = True
            self._file.write(figure_to_html_div_only(fig))

        self._file.write("</div>\n")

    # ------------------------------------------------------------------
    # Sections
    # ------------------------------------------------------------------

    def section(self, name: str) -> "SectionContext":
        """Open a (possibly nested) section. Use as a context manager.

        Sections can nest arbitrarily; the rendered report's client-side
        TOC is built by scanning section data attributes at page load.

        Example:
            >>> with report.section("Stage 1"):
            ...     report.add_text("...")
            ...     with report.section("Sub-stage"):
            ...         report.add_text("...")
        """
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
        """Write the closing tags, close the file, return the final path.

        Idempotent — repeated calls return the same path without error.
        Not needed when the Collector is used as a context manager;
        ``__exit__`` calls this for you.

        Returns:
            For ``inline`` mode, the ``.html`` file path.
            For ``directory`` mode, the directory path.

        Example:
            >>> c = Collector("out.html")
            >>> c.add_text("hi")
            >>> c.save()
            'out.html'
        """
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
