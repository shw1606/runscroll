"""Example: data-migration validation report (handoff §3.3).

Showcases the killer plotly path — interactive distribution comparisons
that work inside the single self-contained file, no server.

Run:
    pip install "runscroll[plotly]" numpy
    python examples/migration_validation.py
"""
from __future__ import annotations

import traceback
from pathlib import Path

import numpy as np

from runscroll import Collector


def _make_distribution_figure(rng: np.random.Generator):
    import plotly.graph_objects as go

    before = rng.normal(loc=100, scale=20, size=4_000)
    after = rng.normal(loc=98, scale=22, size=4_000)
    fig = go.Figure()
    fig.add_trace(go.Histogram(x=before, name="source", opacity=0.65))
    fig.add_trace(go.Histogram(x=after, name="target", opacity=0.65))
    fig.update_layout(
        barmode="overlay",
        title="Distribution: source vs target",
        xaxis_title="value",
        yaxis_title="count",
        height=380,
    )
    return fig


def _validate_table(name: str, rng: np.random.Generator) -> dict:
    src = int(rng.integers(50_000, 200_000))
    mismatches = int(rng.integers(0, 60))
    return {
        "table": name,
        "source_rows": src,
        "target_rows": src - mismatches,
        "mismatches": mismatches,
        "status": "ok" if mismatches == 0 else "diff",
    }


def main() -> Path:
    rng = np.random.default_rng(seed=7)
    out_dir = Path(__file__).parent / "out"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "migration_validation.html"

    migration_id = "mig-20260505-A"
    tables = ["users", "orders", "order_items", "payments", "events"]

    schema_diff = [
        {"column": "users.email_verified", "source": "—", "target": "boolean", "note": "added"},
        {"column": "orders.status", "source": "varchar(16)", "target": "varchar(32)", "note": "widened"},
        {"column": "events.metadata", "source": "json", "target": "jsonb", "note": "type changed"},
    ]

    ok = 0
    failed = 0

    with Collector(out_path, title=f"Migration run {migration_id}") as report:
        with report.section("Pre-flight"):
            report.add_kv(
                {
                    "migration_id": migration_id,
                    "source_db": "postgres://legacy",
                    "target_db": "postgres://primary",
                    "started_at": "2026-05-05T09:00:12Z",
                }
            )
            report.add_table(schema_diff, title="Schema diff (source → target)")

        with report.section("Per-table validation"):
            for table in tables:
                with report.section(table):
                    try:
                        stats = _validate_table(table, rng)
                        report.add_kv(stats)
                        report.add_figure(
                            _make_distribution_figure(rng),
                            title="Distribution before/after",
                            description=f"{table}: source vs target sample",
                        )
                        if stats["mismatches"] > 0:
                            failed += 1
                            sample = [
                                {
                                    "row_id": int(rng.integers(1, stats["source_rows"])),
                                    "column": rng.choice(["amount", "status", "updated_at"]),
                                    "source_value": str(rng.integers(0, 9999)),
                                    "target_value": str(rng.integers(0, 9999)),
                                }
                                for _ in range(min(10, stats["mismatches"]))
                            ]
                            report.add_table(sample, title="Sample mismatches")
                            report.add_text(
                                f"{stats['mismatches']} mismatches in {table}",
                                level="warning",
                            )
                        else:
                            ok += 1
                            report.add_text("clean", level="success")
                    except Exception:
                        report.add_text(
                            traceback.format_exc(), level="error"
                        )
                        failed += 1

        with report.section("Summary"):
            report.add_kv(
                {
                    "tables_ok": ok,
                    "tables_failed": failed,
                    "elapsed_sec": round(float(rng.uniform(180, 360)), 1),
                }
            )
            report.add_text(
                f"validation finished — {ok} ok, {failed} failed",
                level="success" if failed == 0 else "warning",
            )

    return out_path


if __name__ == "__main__":
    out = main()
    size_mb = out.stat().st_size / 1024 / 1024
    print(f"wrote {out} ({size_mb:.2f} MiB)")
