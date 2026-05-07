"""Tests for the ``python -m runscroll demo`` CLI."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest


PY = sys.executable


def _strip_scripts_and_styles(html_str: str) -> str:
    return re.sub(
        r"<(script|style)\b[^>]*>.*?</\1>",
        lambda m: f"<{m.group(1)}></{m.group(1)}>",
        html_str,
        flags=re.DOTALL | re.IGNORECASE,
    )


def test_no_args_prints_help():
    """Running `python -m runscroll` with no subcommand should print the
    help text and exit cleanly."""
    result = subprocess.run(
        [PY, "-m", "runscroll"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    out = result.stdout + result.stderr
    assert "demo" in out


def test_version_flag():
    result = subprocess.run(
        [PY, "-m", "runscroll", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "runscroll" in result.stdout
    assert re.search(r"\d+\.\d+\.\d+", result.stdout)


def test_demo_writes_report_at_out(tmp_path):
    out = tmp_path / "demo.html"
    result = subprocess.run(
        [PY, "-m", "runscroll", "demo", "--out", str(out)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    # stdout should include the path it wrote.
    assert str(out) in result.stdout
    assert out.exists()
    # File is a complete HTML document.
    content = out.read_text()
    assert content.startswith("<!DOCTYPE html>")
    assert content.rstrip().endswith("</html>")


def test_demo_exercises_every_entry_class(tmp_path):
    out = tmp_path / "demo.html"
    subprocess.run(
        [PY, "-m", "runscroll", "demo", "--out", str(out)],
        check=True,
        capture_output=True,
    )
    content = out.read_text()
    # Every entry-class produced by Collector must appear at least once.
    for marker in (
        "rs-text",
        "rs-kv",
        "rs-code",
        "rs-table",
        "rs-image",
        "rs-section",
    ):
        assert marker in content, f"demo output missing {marker!r}"


def test_demo_includes_all_five_levels(tmp_path):
    out = tmp_path / "demo.html"
    subprocess.run(
        [PY, "-m", "runscroll", "demo", "--out", str(out)],
        check=True,
        capture_output=True,
    )
    content = out.read_text()
    for level in ("info", "debug", "warning", "error", "success"):
        assert f"rs-text-{level}" in content


def test_demo_output_is_self_contained(tmp_path):
    out = tmp_path / "demo.html"
    subprocess.run(
        [PY, "-m", "runscroll", "demo", "--out", str(out)],
        check=True,
        capture_output=True,
    )
    content = out.read_text()
    stripped = _strip_scripts_and_styles(content)
    pattern = re.compile(
        r'(?:src|href|srcset|cite|action|data-src)\s*=\s*["\']https?://',
        re.IGNORECASE,
    )
    assert pattern.search(stripped) is None


def test_demo_default_out_path(tmp_path, monkeypatch):
    """With no --out, the demo should write to a default tmp path and
    print it to stdout. We monkeypatch tempfile.gettempdir so the test
    doesn't rely on the system tmp."""
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    result = subprocess.run(
        [PY, "-m", "runscroll", "demo"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    printed = Path(result.stdout.strip())
    assert printed.exists()
    assert printed.name == "runscroll-demo.html"


def test_console_script_runs(tmp_path):
    """The `runscroll` console-script entry point (installed via pip)
    should also work."""
    venv_bin = Path(sys.executable).parent
    runscroll_script = venv_bin / "runscroll"
    if not runscroll_script.exists():
        pytest.skip(f"console script not installed at {runscroll_script}")
    out = tmp_path / "demo.html"
    result = subprocess.run(
        [str(runscroll_script), "demo", "--out", str(out)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert out.exists()
