"""Tests for sections + Collector context manager (Step 8)."""
from __future__ import annotations

import re

import pytest

from runscroll import Collector


def _body(html_str: str) -> str:
    """Return content between <main> and </main>, so we don't count
    the literal string '<section' appearing inside JS comments or CSS."""
    m = re.search(r"<main[^>]*>(.*)</main>", html_str, flags=re.DOTALL)
    assert m, "no <main> block found"
    return m.group(1)


def _count_tag(body: str, tag: str) -> int:
    """Count opening and self-closing occurrences of `<tag>` or `<tag ...>`."""
    return len(re.findall(rf"<{tag}\b", body))


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

def test_section_emits_open_and_close_tags(tmp_path):
    p = tmp_path / "x.html"
    c = Collector(p)
    with c.section("Stage 1"):
        c.add_text("inside")
    c.save()

    body = _body(p.read_text())
    assert _count_tag(body, "section") == 1
    assert body.count("</section>") == 1
    assert "Stage 1" in body
    assert "inside" in body


def test_nested_sections_match_open_close_counts(tmp_path):
    p = tmp_path / "x.html"
    c = Collector(p)
    with c.section("outer"):
        c.add_text("o1")
        with c.section("inner"):
            c.add_text("i1")
            with c.section("deeper"):
                c.add_text("d1")
        c.add_text("o2")
    c.save()

    body = _body(p.read_text())
    assert _count_tag(body, "section") == 3
    assert body.count("</section>") == 3
    opens = [m.start() for m in re.finditer(r"<section\b", body)]
    closes = [m.start() for m in re.finditer(r"</section>", body)]
    assert opens[0] < opens[1] < opens[2] < closes[0] < closes[1] < closes[2]


def test_section_depth_attribute(tmp_path):
    p = tmp_path / "x.html"
    c = Collector(p)
    with c.section("a"):
        with c.section("b"):
            with c.section("c"):
                c.add_text("deep")
    c.save()
    content = p.read_text()
    assert 'data-rs-depth="1"' in content
    assert 'data-rs-depth="2"' in content
    assert 'data-rs-depth="3"' in content


def test_section_id_increments(tmp_path):
    p = tmp_path / "x.html"
    c = Collector(p)
    with c.section("first"):
        pass
    with c.section("second"):
        pass
    c.save()
    content = p.read_text()
    assert 'data-rs-section-id="1"' in content
    assert 'data-rs-section-id="2"' in content


def test_section_name_escaped(tmp_path):
    p = tmp_path / "x.html"
    c = Collector(p)
    with c.section("<x>name"):
        c.add_text("ok")
    c.save()
    content = p.read_text()
    assert "<x>name" not in content
    assert "&lt;x&gt;name" in content


def test_section_h_levels_clamp_at_six(tmp_path):
    """Nested sections beyond depth 5 should still produce valid HTML
    (clamped at h6)."""
    p = tmp_path / "x.html"
    c = Collector(p)
    # depth 1..7 -> h2..h7 unclamped; with clamp -> h2..h6
    with c.section("d1"):
        with c.section("d2"):
            with c.section("d3"):
                with c.section("d4"):
                    with c.section("d5"):
                        with c.section("d6"):
                            with c.section("d7"):
                                c.add_text("deepest")
    c.save()
    content = p.read_text()
    # No h7+ should appear.
    assert "<h7" not in content
    assert "<h8" not in content
    assert "<h6" in content


# ---------------------------------------------------------------------------
# Collector as context manager
# ---------------------------------------------------------------------------

def test_collector_context_manager_saves_on_exit(tmp_path):
    p = tmp_path / "x.html"
    with Collector(p) as c:
        c.add_text("hello")
    # save should have happened automatically.
    content = p.read_text()
    assert content.rstrip().endswith("</html>")
    assert "hello" in content


def test_collector_context_manager_with_section(tmp_path):
    p = tmp_path / "x.html"
    with Collector(p) as c:
        with c.section("S"):
            c.add_text("inside")
    content = p.read_text()
    assert "<section" in content
    assert "</section>" in content
    assert content.rstrip().endswith("</html>")


# ---------------------------------------------------------------------------
# Exception safety
# ---------------------------------------------------------------------------

def test_exception_inside_section_closes_file_to_valid_html(tmp_path):
    p = tmp_path / "x.html"
    with pytest.raises(RuntimeError, match="boom"):
        with Collector(p) as c:
            with c.section("S"):
                c.add_text("before")
                raise RuntimeError("boom")
    content = p.read_text()
    # File ends as valid HTML even though we raised inside.
    assert content.rstrip().endswith("</html>")
    # Section was closed too.
    body = _body(content)
    assert _count_tag(body, "section") == body.count("</section>") == 1


def test_exception_logged_as_error_entry_by_default(tmp_path):
    p = tmp_path / "x.html"
    with pytest.raises(RuntimeError, match="kaboom"):
        with Collector(p) as c:
            c.add_text("normal")
            raise RuntimeError("kaboom")
    content = p.read_text()
    # The traceback should land in an error-level text entry.
    assert "rs-text-error" in content
    assert "kaboom" in content
    assert "RuntimeError" in content


def test_exception_logging_can_be_disabled(tmp_path):
    p = tmp_path / "x.html"
    with pytest.raises(RuntimeError):
        with Collector(p, log_exceptions=False) as c:
            c.add_text("normal")
            raise RuntimeError("silent")
    content = p.read_text()
    assert "silent" not in content
    assert "RuntimeError" not in content
    assert content.rstrip().endswith("</html>")


def test_exception_does_not_swallow(tmp_path):
    """The Collector __exit__ must not return True / swallow the exception."""
    with pytest.raises(ValueError, match="propagate"):
        with Collector(tmp_path / "x.html"):
            raise ValueError("propagate")


def test_unclosed_section_still_closes_on_collector_exit(tmp_path):
    """If the user breaks out without using `with c.section`, the Collector
    should still emit matched section tags on exit (defensive)."""
    p = tmp_path / "x.html"
    c = Collector(p)
    c._open_section("dangling")  # type: ignore[attr-defined]
    c.add_text("inside dangling")
    # Now exit without closing the section (simulate via __exit__).
    c.__exit__(None, None, None)
    content = p.read_text()
    body = _body(content)
    assert _count_tag(body, "section") == body.count("</section>") == 1
    assert content.rstrip().endswith("</html>")


# ---------------------------------------------------------------------------
# Integration with all entry types
# ---------------------------------------------------------------------------

def test_all_entry_types_inside_section(tmp_path):
    p = tmp_path / "x.html"
    with Collector(p, title="integration") as c:
        with c.section("Stage 1"):
            c.add_text("text entry")
            c.add_kv({"k": "v"})
            c.add_code("print('hi')", lang="python")
            c.add_table([{"a": 1, "b": 2}])
            c.add_image(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
    content = p.read_text()
    for marker in (
        "rs-text",
        "rs-kv",
        "rs-code",
        "rs-table",
        "rs-image",
        "rs-section",
    ):
        assert marker in content
    assert content.rstrip().endswith("</html>")
