"""Inline mode self-containment guarantees (handoff §6.1, §11.2).

A runscroll inline-mode HTML report must work fully when opened from disk
with no network: no tag attribute (src / href / srcset / cite / etc.) may
reference a remote URL. We make the check on the document with <script>
and <style> bodies stripped — string literals inside JS or CSS that
happen to look like 'href="https://"' are not network refs.
"""
from __future__ import annotations

import re

import pytest

from runscroll import Collector

_SCRIPT_OR_STYLE = re.compile(
    r"<(script|style)\b[^>]*>.*?</\1>", flags=re.DOTALL | re.IGNORECASE
)


def _strip_scripts_and_styles(html_str: str) -> str:
    """Return the HTML with the *contents* of every <script>...</script>
    and <style>...</style> block removed (the tags stay; just the text
    between them is dropped). Self-containment cares about HTML
    attributes; string literals inside scripts are not network refs."""
    return _SCRIPT_OR_STYLE.sub(
        lambda m: f"<{m.group(1)}></{m.group(1)}>", html_str
    )


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


def test_no_attribute_references_remote_url(rendered):
    """The actual self-containment contract: no tag attribute (src/href/
    srcset/cite/action/data-src) references an http(s):// URL.

    Strings inside <script> or <style> blocks are stripped before the
    check — they're bundle content, not network refs.
    """
    stripped = _strip_scripts_and_styles(rendered)
    pattern = re.compile(
        r'(?:src|href|srcset|cite|action|data-src)\s*=\s*["\']https?://',
        re.IGNORECASE,
    )
    assert pattern.search(stripped) is None


def test_no_css_imports_or_url_refs_to_remote(rendered):
    """@import / url() inside the inline <style> block must not reference
    remote resources. (We do NOT strip <style> here because that's where
    these patterns would actually have effect.)"""
    # Inline <style> block is the one we own; check it.
    m = re.search(r"<style>(.*?)</style>", rendered, flags=re.DOTALL)
    assert m, "expected an inline <style> block"
    css = m.group(1)
    assert re.search(r"@import\s+(?:url\()?\s*['\"]?https?://", css) is None
    assert re.search(r"\burl\(\s*['\"]?https?://", css) is None


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
