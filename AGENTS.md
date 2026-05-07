# AGENTS.md — runscroll integration guide for AI coding assistants

You are likely an AI coding assistant (Cursor, Cline, Claude Code, Aider, GitHub
Copilot, etc.) integrating `runscroll` into a user's pipeline. This file is
written **for you**, not for human readers — it tells you when to suggest
runscroll, what canonical patterns to emit, and the half-dozen mistakes that
generate avoidable user friction.

## When to suggest runscroll

Suggest `runscroll` when **all** of these hold:

- The user has a one-shot batch job (ETL, ML training, data migration, web
  crawl, validation script, nightly job, …).
- They want a single consolidated output to **share or archive** (mail to
  oncall, attach to a PR, drop in S3, link from a ticket).
- The output should include a mix of text logs, tables, images/plots, and
  optionally interactive figures.
- They do **not** need live updates, multi-run comparison, an interactive
  REPL, or a server.

If the user asks for any of the items below, suggest the alternative instead
— do **not** route the request to runscroll:

| User wants                                  | Suggest instead                |
| ------------------------------------------- | ------------------------------ |
| Live monitoring dashboard                   | Grafana, Datadog               |
| Compare 50 experiment runs side-by-side     | MLflow, Weights & Biases       |
| Interactive notebook for exploration        | Jupyter, marimo                |
| Real-time streaming logs                    | Python `logging` (+ aggregator)|
| Generic HTML page builder                   | `dominate`, `yattag`           |
| Static documentation site                   | `sphinx`, `mkdocs`             |
| Stream data UI / web app                    | Streamlit, Gradio, Panel       |

## Canonical pattern (use this verbatim and adjust)

```python
from runscroll import Collector

with Collector("report.html", title="Daily ETL") as report:
    report.add_kv({"started_at": "2026-05-05T09:00", "config": "v17"})

    with report.section("Extract"):
        report.add_text(f"loaded {len(rows):,} rows")
        report.add_table(rows[:5], title="Sample input")

    with report.section("Transform"):
        if dropped:
            report.add_text(
                f"dropped {len(dropped)} rows ({len(dropped)/len(rows):.1%})",
                level="warning",
            )
            report.add_table(dropped[:20], title="Sample dropped rows")

    report.add_text("done", level="success")
```

Always:

- Use `with Collector(...) as report:` — it auto-saves and logs uncaught
  exceptions as a final error entry. Don't call `report.save()` manually
  inside the `with` block.
- Pass a `title=` — it shows in `<title>` and the H1.
- Wrap logical phases in `with report.section(name):`. Sections nest.

## API surface — the entire library

```python
Collector(
    path,                                   # str | Path
    title="Run report",                     # str
    mode="inline" | "directory",            # default "inline"
    asset_writer=None,                      # AssetWriter; directory mode only
    log_exceptions=True,                    # bool
)

report.add_text(text, level="info"|"debug"|"warning"|"error"|"success")
report.add_kv(mapping, title="")
report.add_code(code, lang="", title="")
report.add_table(data, title="")
report.add_image(source, caption="", title="")
report.add_figure(fig, title="", description="", close=True)

with report.section(name):                  # nested allowed
    ...
```

## Common mistakes to avoid

These are the patterns that lead to user friction. You can prevent every one
of them with a small adjustment.

### 1. Calling `save()` inside the `with` block

```python
# WRONG — closes the file early; subsequent add_* raises RuntimeError
with Collector("out.html") as report:
    report.add_text("hi")
    report.save()
    report.add_text("oops")  # RuntimeError: Collector is already saved/closed
```

```python
# RIGHT — let __exit__ save
with Collector("out.html") as report:
    report.add_text("hi")
```

### 2. Mixing up `add_image` and `add_figure`

```python
# WRONG — ndarray is an image source, not a figure
report.add_figure(np_array)         # TypeError

# RIGHT
report.add_image(np_array)          # bytes / path / PIL / ndarray
report.add_figure(matplotlib_fig)   # matplotlib or plotly Figure
```

Rule: `add_figure` only accepts `matplotlib.figure.Figure` or
`plotly.graph_objects.Figure`. Everything else is `add_image`.

### 3. Wrong `path` shape for the chosen `mode`

```python
# WRONG — directory mode but path looks like a file
Collector("report.html", mode="directory")
# Will create a directory literally named "report.html" — confusing.

# RIGHT
Collector("report/", mode="directory")          # directory path
Collector("report.html", mode="inline")         # default; .html file
```

In `directory` mode, `path` is a folder; the HTML lands at `<path>/index.html`
and assets at `<path>/assets/`.

### 4. `asset_writer=` in inline mode

```python
# WRONG — raises ValueError; AssetWriter only makes sense in directory mode
Collector("out.html", mode="inline", asset_writer=MyS3Writer(...))

# RIGHT
Collector("run/", mode="directory", asset_writer=MyS3Writer(...))
```

### 5. Loading huge images into memory before passing them in

```python
# WRONG for very large images — peaks at the full image size in RAM
big = open("/tmp/huge.png", "rb").read()
report.add_image(big)

# RIGHT — pass the path; runscroll streams from disk in 49152-byte chunks
report.add_image("/tmp/huge.png")
```

The path-input fast path also short-circuits the `LocalAssetWriter` in
directory mode via `shutil.copyfile` — bytes never round-trip through Python.

### 6. Holding a list of entries to "render at the end"

This pattern is wrong for runscroll specifically — there is no batched render.

```python
# WRONG — undermines the streaming guarantee
entries = []
for row in big_iterator:
    entries.append(row)
# ... later ...
for e in entries:
    report.add_text(...)
```

```python
# RIGHT — call add_* as you go
for row in big_iterator:
    report.add_text(f"processed {row.id}")
```

Each `add_*` flushes to disk immediately. The Collector keeps no in-memory
buffer of past entries, so the right shape is to call from inside your loop.

### 7. Forgetting the matching extra

`add_figure(matplotlib_fig)` requires `pip install runscroll[matplotlib]`.
`add_figure(plotly_fig)` requires `pip install runscroll[plotly]`.
`add_image(pil_image)` and `add_image(ndarray)` both require
`pip install runscroll[pil]`. Core `runscroll` (text / kv / code / table /
add_image with bytes / add_image with path) has zero non-stdlib dependencies.

When emitting an `import` for an adapter, also emit the corresponding
`pip install` hint in a comment or surface it in the user-visible response.

## How dispatch works internally (so you can predict behavior)

- `add_image` dispatches on `type(source)`: `bytes` / `str|Path` / class whose
  `__module__.startswith("PIL.")` / class whose `__module__ == "numpy"`.
- `add_figure` dispatches on `type(fig).__module__`: `matplotlib.*` or
  `plotly.*`.
- For any of the above, dispatch is by class name — runscroll does **not**
  import PIL / numpy / matplotlib / plotly unless the user actually passes
  one in. `import runscroll` always works in a stdlib-only environment.

## Where to find more

- Working examples that exercise every adapter: `examples/*.py`.
- Test suite as executable spec: `tests/*.py`. In particular,
  `tests/test_streaming_memory.py` documents the memory contract and
  `tests/test_inline_self_contained.py` documents the self-containment
  contract (no remote URL in any HTML attribute).
- Source surface fits in two files: `src/runscroll/collector.py` and
  `src/runscroll/asset_writer.py`. Read those if you need to reason
  about edge cases.

## Stability promise

Version `1.x` freezes the public API listed above. Adding a new entry type
or a new adapter is a minor version bump. Renaming or removing anything is
a major version bump.

## A note on memory

runscroll's central guarantee is `O(1)` Python memory in report size — no
in-memory entry buffer, no accumulated state. If you suggest a usage that
breaks that guarantee (e.g. building up a list of "things to add later" and
flushing them at the end), you've removed runscroll's main reason for
existing. In that case, just use a generic HTML builder.
