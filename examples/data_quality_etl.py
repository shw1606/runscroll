"""Example: daily ETL with data-quality post-mortem (handoff §3.2).

Run:
    pip install "runscroll[matplotlib]" numpy
    python examples/data_quality_etl.py

Each daily run produces one HTML at examples/out/etl-YYYY-MM-DD.html.
The intended deployment pattern: the worker mails this file to oncall
(or uploads it and posts a link). No infra needed.
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from runscroll import Collector


def _mock_extract(rng: np.random.Generator) -> list[dict]:
    """Pretend we extracted N rows from somewhere."""
    n = int(rng.integers(45_000, 55_000))
    rows = [
        {
            "id": i,
            "hour": int(rng.integers(0, 24)),
            "amount": round(rng.lognormal(mean=3.5, sigma=0.7), 2),
            "currency": rng.choice(["USD", "EUR", "JPY"]),
            "user_id": int(rng.integers(1, 5_000)),
        }
        for i in range(n)
    ]
    return rows


def _clean(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    cleaned, dropped = [], []
    for r in rows:
        if r["amount"] <= 0 or r["amount"] > 10_000:
            dropped.append({**r, "drop_reason": "amount out of range"})
            continue
        if r["currency"] not in ("USD", "EUR", "JPY"):
            dropped.append({**r, "drop_reason": "unknown currency"})
            continue
        cleaned.append(r)
    return cleaned, dropped


def _plot_hourly_volume(rows: list[dict]) -> plt.Figure:
    counts = np.zeros(24, dtype=int)
    for r in rows:
        counts[r["hour"]] += 1
    fig, ax = plt.subplots(figsize=(7, 3.2))
    ax.bar(range(24), counts, color="#6aa1ea")
    ax.set_xlabel("hour")
    ax.set_ylabel("rows")
    ax.set_title("Volume by hour (raw extract)")
    ax.grid(alpha=0.3, axis="y")
    return fig


def _plot_amount_distribution(rows: list[dict]) -> plt.Figure:
    amounts = np.array([r["amount"] for r in rows])
    fig, ax = plt.subplots(figsize=(7, 3.2))
    ax.hist(amounts, bins=60, color="#5fc7a4", alpha=0.85)
    ax.set_xlabel("amount")
    ax.set_ylabel("count")
    ax.set_title("Amount distribution (post-clean)")
    ax.grid(alpha=0.3, axis="y")
    return fig


def main() -> Path:
    rng = np.random.default_rng(seed=20260505)
    today = date.today()

    out_dir = Path(__file__).parent / "out"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"etl-{today.isoformat()}.html"

    with Collector(out_path, title=f"Daily ETL — {today.isoformat()}") as report:
        report.add_kv(
            {
                "started_at": datetime.utcnow().isoformat(timespec="seconds"),
                "config_version": "v17",
                "warehouse": "snowflake://prod/etl_main",
            }
        )

        with report.section("Extract"):
            raw = _mock_extract(rng)
            report.add_text(f"loaded {len(raw):,} rows")
            report.add_table(raw[:5], title="Sample input")
            report.add_figure(
                _plot_hourly_volume(raw),
                title="Volume by hour",
            )

        with report.section("Transform"):
            cleaned, dropped = _clean(raw)
            ratio = len(dropped) / len(raw) if raw else 0
            report.add_text(
                f"cleaned {len(cleaned):,} rows — "
                f"dropped {len(dropped):,} ({ratio:.1%})",
                level="warning" if ratio > 0.001 else "info",
            )
            if dropped:
                report.add_table(
                    dropped[:20],
                    title="Sample dropped rows",
                )
            report.add_figure(
                _plot_amount_distribution(cleaned),
                title="Amount dist (post-clean)",
            )

        with report.section("Load"):
            inserted = int(len(cleaned) * 0.94)
            updated = len(cleaned) - inserted
            report.add_kv(
                {
                    "inserted": f"{inserted:,}",
                    "updated": f"{updated:,}",
                    "elapsed_sec": round(rng.uniform(120, 240), 1),
                },
                title="Warehouse write stats",
            )

        report.add_text("ETL OK", level="success")

    return out_path


if __name__ == "__main__":
    out = main()
    print(f"wrote {out} ({out.stat().st_size/1024:.0f} KiB)")
