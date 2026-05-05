# runscroll

> **runscroll — turn one batch run into one scrollable HTML report.**
>
> Sprinkle `report.add_*()` calls through your batch job. Get a single
> self-contained HTML file out the other side. Mail it, drop it in S3, attach
> it to a PR. No server, no account, no infrastructure.

## Status

Alpha. The public API is being built up step by step; see commit history.

## Install

```bash
pip install runscroll
# with adapters you actually use:
pip install "runscroll[matplotlib,pandas,pil]"
```

## Quick taste (target API)

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

## License

MIT.
