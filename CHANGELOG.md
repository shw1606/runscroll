# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.0.1] — 2026-05-07

Documentation-only patch over 1.0.0. No code changes; the public API is
unchanged.

### Fixed

- README example screenshots were broken on the PyPI project page —
  PyPI's renderer does not auto-resolve relative image paths against
  the configured `Repository` URL. Switched to absolute
  `https://raw.githubusercontent.com/shw1606/runscroll/main/...`
  references so the four recipe screenshots render correctly on PyPI,
  GitHub, IDE markdown previews, and any other consumer.

### Added

- PyPI version / Python-versions / License badges at the top of the
  README so the package's status is legible at a glance from both
  GitHub and PyPI.

## [1.0.0] — 2026-05-07

First public release. The public API listed below is **frozen for the
1.x line** — additions go in minor versions, breaking changes wait for
2.0.0.

### Public API (frozen)

- `Collector(path, title, mode, asset_writer, log_exceptions)` —
  context manager.
- `Collector.add_text(text, level)` — info / debug / warning / error /
  success.
- `Collector.add_kv(mapping, title)` — two-column key/value block.
- `Collector.add_code(code, lang, title)` — preformatted block.
- `Collector.add_table(data, title)` — list[dict] or list[list/tuple].
- `Collector.add_image(source, caption, title)` — bytes / path /
  PIL.Image / numpy.ndarray.
- `Collector.add_figure(fig, title, description, close)` —
  matplotlib.figure.Figure or plotly.graph_objects.Figure.
- `Collector.section(name)` — nested context manager.
- `AssetWriter` Protocol + `LocalAssetWriter` implementation.

### Features

- **Streaming append-write architecture** — `O(1)` Python memory
  regardless of report size. Each `add_*` call serializes its content
  to the open file and flushes; no in-memory entry buffer.
- **Two output modes** — `inline` (single self-contained `.html` with
  base64-embedded assets) and `directory` (`index.html` + `assets/`
  with relative URLs). `AssetWriter` Protocol lets users plug in
  S3 / GCS / sftp / etc. without runscroll importing any cloud SDK.
- **Adapters as optional extras** — matplotlib, plotly, Pillow, numpy.
  `import runscroll` succeeds in a stdlib-only environment; adapters
  load lazily only when their input type is dispatched.
- **Plotly bundle de-duplication** — the ~5 MiB plotly.js bundle is
  inlined exactly once per Collector regardless of how many plotly
  figures are added.
- **Client-side TOC, search, level filter, dark/light theme toggle,
  and error/warning count badges** — built at page load by the
  inline JS scanning `<section data-rs-section-id>` and `.rs-text-*`
  nodes, so Python never has to know all sections in advance.
- **Context-manager API** with auto-save on `__exit__` and (default-on)
  exception logging that captures any uncaught traceback as a final
  `rs-text-error` entry before closing the file.
- **`runscroll demo` CLI / `python -m runscroll demo`** — renders a
  representative report exercising every entry type. Useful for
  smoke-testing an installation.

### Tested with

Python 3.9 / 3.10 / 3.11 / 3.12 — `matplotlib >= 3.5`, `plotly >= 5.0`,
`Pillow >= 9.0`. 117 test cases including a memory-safety gate
(`tests/test_streaming_memory.py`) that fails the build if anyone
introduces an in-memory entry buffer or pins large payloads.

### Known limits (deferred to a later version)

- pandas / bokeh / Pygments adapters — pattern is established, just
  not in 1.0.
- `add_diff` entry type — present in design notes, not in 1.0.
- AssetWriter Protocol is bytes-only; for huge non-path inputs in
  directory mode, peak memory is `O(payload)`. Streaming variant
  Protocol planned.
- Self-hosted documentation site. README + AGENTS.md + llms.txt cover
  v1.0; mkdocs-style site can come later.

[1.0.1]: https://github.com/shw1606/runscroll/releases/tag/v1.0.1
[1.0.0]: https://github.com/shw1606/runscroll/releases/tag/v1.0.0
