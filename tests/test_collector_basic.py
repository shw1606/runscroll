"""Smoke tests for the Collector skeleton (Step 2).

These cover the streaming append-write contract at the surface level. The
deeper memory-safety guarantees are exercised in test_streaming_memory.py
(introduced in Step 3).
"""
from __future__ import annotations

import pytest

from runscroll import Collector


def test_collector_creates_file_at_construction(tmp_path):
    p = tmp_path / "report.html"
    assert not p.exists()
    c = Collector(p, title="Test report")
    assert p.exists()
    # Header should be on disk before any add_* call.
    assert p.stat().st_size > 0
    c.save()


def test_add_text_is_visible_on_disk_before_save(tmp_path):
    """Streaming contract: an entry hits disk during add_*, not at save()."""
    p = tmp_path / "report.html"
    c = Collector(p, title="Streaming check")

    size_after_header = p.stat().st_size
    c.add_text("first entry")
    size_after_one_entry = p.stat().st_size
    assert size_after_one_entry > size_after_header

    c.add_text("second entry")
    size_after_two_entries = p.stat().st_size
    assert size_after_two_entries > size_after_one_entry

    c.save()


def test_full_document_structure(tmp_path):
    p = tmp_path / "report.html"
    c = Collector(p, title="Doc")
    c.add_text("hello")
    c.add_text("warn", level="warning")
    final = c.save()

    assert final == str(p)
    content = p.read_text(encoding="utf-8")
    assert content.startswith("<!DOCTYPE html>")
    assert "<title>Doc</title>" in content
    assert "hello" in content
    assert "warn" in content
    assert "rs-text-warning" in content
    assert content.rstrip().endswith("</html>")


def test_html_escapes_dangerous_input(tmp_path):
    p = tmp_path / "report.html"
    c = Collector(p)
    c.add_text("<script>alert('xss')</script>")
    c.add_text("<b>bold</b>", level="error")
    c.save()

    content = p.read_text(encoding="utf-8")
    # The literal payloads must not appear unescaped inside <main>.
    assert "<script>alert(" not in content
    assert "<b>bold</b>" not in content
    # Their escaped forms should.
    assert "&lt;script&gt;" in content
    assert "&lt;b&gt;bold&lt;/b&gt;" in content


def test_title_is_escaped(tmp_path):
    p = tmp_path / "report.html"
    c = Collector(p, title="<x>&y")
    c.save()
    content = p.read_text(encoding="utf-8")
    assert "<title><x>&y</title>" not in content
    assert "&lt;x&gt;&amp;y" in content


def test_invalid_level_raises(tmp_path):
    c = Collector(tmp_path / "x.html")
    with pytest.raises(ValueError):
        c.add_text("oops", level="catastrophic")  # type: ignore[arg-type]
    c.save()


def test_save_is_idempotent(tmp_path):
    p = tmp_path / "report.html"
    c = Collector(p)
    c.add_text("only entry")
    first = c.save()
    second = c.save()
    assert first == second == str(p)


def test_add_after_save_raises(tmp_path):
    c = Collector(tmp_path / "x.html")
    c.save()
    with pytest.raises(RuntimeError):
        c.add_text("too late")


def test_creates_parent_directory(tmp_path):
    p = tmp_path / "nested" / "deep" / "report.html"
    c = Collector(p)
    c.save()
    assert p.exists()
