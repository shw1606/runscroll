"""Smoke tests for example scripts: each main() runs end-to-end and writes
a non-trivial self-contained HTML. These also serve as integration tests
across the full Collector + adapters surface.
"""
from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


@pytest.fixture(autouse=True)
def _add_examples_dir(monkeypatch):
    monkeypatch.syspath_prepend(str(EXAMPLES))


def _strip_scripts_and_styles(html_str: str) -> str:
    return re.sub(
        r"<(script|style)\b[^>]*>.*?</\1>",
        lambda m: f"<{m.group(1)}></{m.group(1)}>",
        html_str,
        flags=re.DOTALL | re.IGNORECASE,
    )


def _assert_self_contained(html_str: str) -> None:
    stripped = _strip_scripts_and_styles(html_str)
    pattern = re.compile(
        r'(?:src|href|srcset|cite|action|data-src)\s*=\s*["\']https?://',
        re.IGNORECASE,
    )
    assert pattern.search(stripped) is None


def _import_example(name: str):
    # Force re-import so the example's module-level state is fresh
    # between tests if any.
    if name in sys.modules:
        del sys.modules[name]
    return importlib.import_module(name)


def test_ml_training_run_smoke():
    pytest.importorskip("matplotlib")
    pytest.importorskip("numpy")
    pytest.importorskip("PIL")
    mod = _import_example("ml_training_run")
    out = Path(mod.main())
    assert out.exists()
    assert out.stat().st_size > 10_000
    content = out.read_text()
    assert content.rstrip().endswith("</html>")
    assert "rs-figure" in content
    assert "rs-table" in content
    assert "rs-image" in content
    _assert_self_contained(content)


def test_data_quality_etl_smoke():
    pytest.importorskip("matplotlib")
    pytest.importorskip("numpy")
    mod = _import_example("data_quality_etl")
    out = Path(mod.main())
    assert out.exists()
    assert out.stat().st_size > 10_000
    content = out.read_text()
    assert content.rstrip().endswith("</html>")
    assert "Volume by hour" in content
    _assert_self_contained(content)


def test_migration_validation_smoke():
    pytest.importorskip("plotly")
    pytest.importorskip("numpy")
    mod = _import_example("migration_validation")
    out = Path(mod.main())
    assert out.exists()
    # plotly bundle inlined once -> file is multi-MB.
    assert out.stat().st_size > 1_000_000
    content = out.read_text()
    assert content.rstrip().endswith("</html>")
    # Plot.ly bundle de-dup: the v-banner appears exactly once.
    assert content.count("plotly.js v") == 1
    _assert_self_contained(content)


def test_web_scraper_smoke():
    pytest.importorskip("matplotlib")
    pytest.importorskip("numpy")
    mod = _import_example("web_scraper")
    out = Path(mod.main())
    assert out.exists()
    assert out.stat().st_size > 10_000
    content = out.read_text()
    assert content.rstrip().endswith("</html>")
    assert "HTTP status breakdown" in content
    _assert_self_contained(content)
