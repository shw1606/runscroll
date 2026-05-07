"""Command-line entry: ``python -m runscroll`` / ``runscroll`` script.

Currently exposes one subcommand:

    runscroll demo [--out PATH]

which renders a representative report exercising every entry type and
prints the absolute output path. Useful for:

  - smoke-testing an installation (``pip install runscroll && runscroll demo``)
  - showing AI agents what the rendered output looks like
  - sanity-checking after upgrades

The demo runs in any environment — only the figure section is skipped if
matplotlib isn't available. No optional extras are required for the rest.
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

from . import __version__
from .collector import Collector

# A tiny valid PNG (1x1 transparent pixel) — used so the image entry has
# real bytes even when Pillow isn't installed.
_TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c63f8ffff3f000005fe02fea3b13f56000000004945"
    "4e44ae426082"
)


def _try_matplotlib_figure():
    """Return a small matplotlib Figure if matplotlib is installed, else None."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return None
    fig, ax = plt.subplots(figsize=(6, 3.2))
    ax.plot([0, 1, 2, 3, 4], [1.0, 0.62, 0.41, 0.30, 0.24], marker="o")
    ax.set_xlabel("epoch")
    ax.set_ylabel("loss")
    ax.set_title("Demo loss curve")
    ax.grid(alpha=0.3)
    return fig


def render_demo(out_path: Path) -> Path:
    """Build a representative demo report at ``out_path`` and return the path.

    Exercises text levels (info / debug / warning / error / success), kv,
    code, table (list[dict] and list[list]), image (bytes), figure
    (matplotlib if present), and nested sections.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with Collector(out_path, title=f"runscroll {__version__} demo") as report:
        report.add_kv(
            {
                "runscroll": __version__,
                "python": sys.version.split()[0],
                "platform": sys.platform,
            },
            title="Environment",
        )

        with report.section("Text levels"):
            report.add_text("info — ordinary log line")
            report.add_text("debug — verbose detail", level="debug")
            report.add_text("warning — something unusual", level="warning")
            report.add_text("error — a failure (no exception raised)", level="error")
            report.add_text("success — milestone reached", level="success")

        with report.section("Tables"):
            report.add_table(
                [
                    {"name": "alice", "score": 0.91, "label": "ok"},
                    {"name": "bob", "score": 0.78, "label": "review"},
                    {"name": "carol", "score": 0.95, "label": "ok"},
                ],
                title="list[dict] — keys become columns",
            )
            report.add_table(
                [[1, 2, 3], [4, 5, 6], [7, 8, 9]],
                title="list[list] — bare grid",
            )

        with report.section("Code blocks"):
            report.add_code(
                "select count(*) from events where day = current_date",
                lang="sql",
                title="Validation query",
            )
            report.add_code(
                "for row in cursor:\n    process(row)",
                lang="python",
            )

        with report.section("Images and figures"):
            report.add_image(_TINY_PNG, caption="1x1 PNG (bytes path)")
            fig = _try_matplotlib_figure()
            if fig is not None:
                report.add_figure(
                    fig,
                    title="matplotlib Figure",
                    description="install runscroll[matplotlib] for this section",
                )
            else:
                report.add_text(
                    "matplotlib not installed — figure section skipped. "
                    "`pip install runscroll[matplotlib]` to include it.",
                    level="debug",
                )

        with report.section("Nested sections"):
            with report.section("Outer"):
                report.add_text("at depth 2")
                with report.section("Inner"):
                    report.add_text("at depth 3")

        report.add_text("demo complete", level="success")

    return out_path


def _cmd_demo(args: argparse.Namespace) -> int:
    if args.out:
        out = Path(args.out).expanduser().resolve()
    else:
        # Default: a sensibly-named temp file the user can rerun safely.
        out = Path(tempfile.gettempdir()) / "runscroll-demo.html"
    render_demo(out)
    print(out)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="runscroll",
        description=(
            "runscroll command-line entry. Currently exposes a single demo "
            "subcommand that renders a representative report."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"runscroll {__version__}",
    )

    sub = parser.add_subparsers(dest="cmd", required=False)
    demo = sub.add_parser(
        "demo",
        help="render a demo report exercising every entry type",
    )
    demo.add_argument(
        "--out",
        default=None,
        help="output path (default: <tmpdir>/runscroll-demo.html)",
    )
    demo.set_defaults(func=_cmd_demo)

    args = parser.parse_args(argv)
    if args.cmd is None:
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
