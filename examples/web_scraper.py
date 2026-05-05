"""Example: web crawler / scraper run report.

Single-run post-mortem of a crawler. Demonstrates the value over plain
logs: per-failure detail (URL, status, sample of body) is browsable in
a single file, not buried in 20k log lines.

Run:
    pip install "runscroll[matplotlib]" numpy
    python examples/web_scraper.py
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from runscroll import Collector


STATUS_DISTRIBUTION = {
    200: 0.86,
    301: 0.05,
    302: 0.04,
    404: 0.02,
    429: 0.01,
    500: 0.01,
    503: 0.01,
}


def _simulate_crawl(rng: np.random.Generator, n_urls: int) -> list[dict]:
    statuses = list(STATUS_DISTRIBUTION.keys())
    weights = list(STATUS_DISTRIBUTION.values())
    out = []
    for i in range(n_urls):
        s = int(rng.choice(statuses, p=weights))
        out.append(
            {
                "url": f"https://example.com/page-{i:04d}",
                "status": s,
                "elapsed_ms": int(rng.integers(50, 1500)),
                "size_kb": round(float(rng.normal(120, 30)), 1) if s == 200 else 0,
            }
        )
    return out


def _plot_status_breakdown(results: list[dict]) -> plt.Figure:
    by_status: dict[int, int] = {}
    for r in results:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    statuses = sorted(by_status.keys())
    counts = [by_status[s] for s in statuses]
    colors = [
        "#5fc7a4" if s == 200 else "#e2c067" if s < 400 else "#ee5e5e"
        for s in statuses
    ]
    fig, ax = plt.subplots(figsize=(6.5, 3.2))
    ax.bar([str(s) for s in statuses], counts, color=colors)
    ax.set_title("HTTP status breakdown")
    ax.set_ylabel("requests")
    ax.grid(alpha=0.3, axis="y")
    return fig


def _plot_latency(results: list[dict]) -> plt.Figure:
    latencies = np.array([r["elapsed_ms"] for r in results])
    fig, ax = plt.subplots(figsize=(6.5, 3.2))
    ax.hist(latencies, bins=40, color="#6aa1ea", alpha=0.9)
    ax.set_xlabel("elapsed_ms")
    ax.set_ylabel("requests")
    ax.set_title("Per-request latency")
    ax.grid(alpha=0.3, axis="y")
    return fig


def main() -> Path:
    rng = np.random.default_rng(seed=11)
    out_dir = Path(__file__).parent / "out"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "web_scraper.html"

    n_urls = 600
    results = _simulate_crawl(rng, n_urls)

    successes = [r for r in results if r["status"] == 200]
    redirects = [r for r in results if 300 <= r["status"] < 400]
    failures = [r for r in results if r["status"] >= 400]

    with Collector(out_path, title=f"Crawl run — {n_urls} URLs") as report:
        report.add_kv(
            {
                "started_at": datetime.utcnow().isoformat(timespec="seconds"),
                "n_urls": n_urls,
                "concurrency": 8,
                "user_agent": "runscroll-example/1.0",
            }
        )

        with report.section("Overview"):
            report.add_text(
                f"completed: {len(successes)} ok / "
                f"{len(redirects)} redirected / "
                f"{len(failures)} failed",
                level="info",
            )
            report.add_figure(
                _plot_status_breakdown(results), title="HTTP status breakdown"
            )
            report.add_figure(
                _plot_latency(results), title="Per-request latency"
            )

        with report.section("Failures"):
            if failures:
                report.add_text(
                    f"{len(failures)} URLs failed", level="warning"
                )
                report.add_table(
                    sorted(failures, key=lambda r: r["status"], reverse=True),
                    title="All failed requests",
                )
            else:
                report.add_text("no failures", level="success")

        with report.section("Top slow successes"):
            slow = sorted(
                successes, key=lambda r: r["elapsed_ms"], reverse=True
            )[:10]
            report.add_table(slow, title="Top 10 slowest 200s")

        with report.section("Sample of every status code"):
            seen: set[int] = set()
            samples: list[dict] = []
            for r in results:
                if r["status"] not in seen:
                    seen.add(r["status"])
                    samples.append(r)
            report.add_table(samples, title="One example per HTTP status")

        report.add_text("crawl run complete", level="success")

    return out_path


if __name__ == "__main__":
    out = main()
    print(f"wrote {out} ({out.stat().st_size/1024:.0f} KiB)")
