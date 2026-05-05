"""Inline mode self-containment guarantees (handoff §6.1, §11.2).

A runscroll inline-mode HTML report must work fully when opened from disk
with no network: no external stylesheets, no remote scripts, no remote
images, no `@import` chains, no CDN fetches. These tests enforce that
contract by parsing the rendered HTML.
"""
from __future__ import annotations

import re

import pytest

from runscroll import Collector


@pytest.fixture
def rendered(tmp_path):
    p = tmp_path / "report.html"
    c = Collector(p, title="Self-containment check")
    c.add_text("info entry")
    c.add_text("warning entry", level="warning")
    c.add_text("error entry", level="error")
    c.save()
    return p.read_text(encoding="utf-8")


def test_no_external_link_tags(rendered):
    # <link href=...> with anything other than data: would be an external ref.
    assert re.search(r"<link\b[^>]*\bhref=", rendered) is None


def test_no_external_script_src(rendered):
    # <script src=...> always pulls something external (or relative).
    assert re.search(r"<script\b[^>]*\bsrc=", rendered) is None


def test_no_remote_urls(rendered):
    # No http(s):// references anywhere in the document.
    assert "http://" not in rendered
    assert "https://" not in rendered


def test_no_css_imports(rendered):
    # @import inside the inlined <style> would also pull external resources.
    assert "@import" not in rendered


def test_inline_style_block_present_and_substantial(rendered):
    m = re.search(r"<style>(.*?)</style>", rendered, flags=re.DOTALL)
    assert m is not None, "rendered HTML must contain an inline <style> block"
    css = m.group(1)
    # We expect at least the level classes from runscroll.css.
    assert ".rs-text-warning" in css
    assert ".rs-text-error" in css
    # Sentinel token must have been substituted.
    assert "__RUNSCROLL_CSS__" not in rendered


def test_inline_script_block_present(rendered):
    m = re.search(r"<script>(.*?)</script>", rendered, flags=re.DOTALL)
    assert m is not None
    js = m.group(1)
    # Step 4 ships an empty entry-point IIFE; just check it's there and the
    # sentinel got replaced.
    assert "runscroll" in js.lower() or "(function" in js
    assert "__RUNSCROLL_JS__" not in rendered


def test_title_is_escaped_in_template_path(tmp_path):
    p = tmp_path / "report.html"
    c = Collector(p, title="<x>&y")
    c.save()
    content = p.read_text(encoding="utf-8")
    # Sentinel token replacement runs raw replace, but render_header()
    # html-escapes the title before substitution, so the escaped form must
    # be what's on disk.
    assert "<title><x>&y</title>" not in content
    assert "&lt;x&gt;&amp;y" in content


def test_generated_timestamp_emitted(rendered):
    # The header should include some indication of when it was generated.
    # We don't pin the exact value, but the format from render_header is
    # an ISO-like timestamp.
    assert re.search(r"Generated \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", rendered)
