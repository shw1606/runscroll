# runscroll

> **runscroll — turn one batch run into one scrollable HTML report.**
>
> Sprinkle `report.add_*()` calls through your batch job. Get a single
> self-contained HTML file out the other side. Mail it, drop it in S3, attach
> it to a PR. No server, no account, no infrastructure.

## Install

```bash
pip install runscroll
# with the adapters you actually use:
pip install "runscroll[matplotlib,plotly,pandas,pil]"
```

## Quick taste

```python
from runscroll import Collector

with Collector("run.html", title="Daily ETL") as report:
    report.add_text("Starting…")
    with report.section("Extract"):
        report.add_kv({"rows": 1_234_567})
        report.add_table(sample_rows)
    with report.section("Transform"):
        report.add_figure(plot_distribution(df), title="Amount dist")
    report.add_text("done", level="success")
# run.html — single self-contained file, ready to mail / upload / attach.
```

## Why a separate library

Not a generic HTML builder. Strong opinions on **one** scenario:
the post-mortem of **a single batch run** as **a single self-contained file**,
streamed to disk so memory stays flat regardless of report size.

- Not Jupyter (no kernel, drops into existing pipeline code).
- Not MLflow / W&B (no server, no account, no domain lock-in).
- Not Grafana / Datadog (per-record details, not aggregate metrics).
- Not plain logging (images, plots, tables — not just text).

## What you get

| `add_*` method | input |
|---|---|
| `add_text(text, level=…)`   | `info` / `debug` / `warning` / `error` / `success` |
| `add_kv(mapping)`            | dict |
| `add_code(code, lang=…)`     | string |
| `add_table(data)`            | list[dict] / list[list] / list[tuple] |
| `add_image(source)`          | bytes / file path / `PIL.Image` / `numpy.ndarray` |
| `add_figure(fig)`            | matplotlib `Figure` / plotly `Figure` |
| `with report.section(name):` | nested, context-manager based |

Everything runs through a single streaming append-write pipeline:
each call serializes its content directly into the HTML file. **No in-memory
entry buffer** — peak RSS stays bounded regardless of how many or how
large the entries get.

## Output modes

```python
# inline — one .html file, all assets base64'd in (default)
Collector("report.html", mode="inline")

# directory — index.html + assets/ folder; works as a static site
Collector("report/", mode="directory")

# directory + custom destination — plug in S3 / GCS via AssetWriter
Collector("report/", mode="directory", asset_writer=MyS3Writer(...))
```

The `AssetWriter` protocol is a single method:

```python
class AssetWriter(Protocol):
    def write(self, relative_path: str, content: bytes) -> None: ...
```

That's all the library needs to know — authentication, region, retries,
caching are entirely your concern.

## Examples

Working scripts that exercise the full surface — drop them next to your
actual pipeline as a starting point:

- [`examples/ml_training_run.py`](examples/ml_training_run.py) — training-loop
  post-mortem with loss curves, confusion matrix, sample wrong predictions.
- [`examples/data_quality_etl.py`](examples/data_quality_etl.py) — daily ETL
  with hourly volumes, drop-rate warnings, sample dropped rows.
- [`examples/migration_validation.py`](examples/migration_validation.py) —
  per-table migration validation with **interactive plotly distributions**
  (zoom / pan / hover, all in one self-contained file).
- [`examples/web_scraper.py`](examples/web_scraper.py) — crawler run with
  status breakdown, latency histogram, all failed URLs browsable.

## Status

Alpha. API surface is fixed; bugfixes / docs welcome.

## License

MIT.
