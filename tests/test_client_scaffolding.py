"""Tests for the Step 9 client-side scaffolding.

We can't run the inline JS without a headless browser, but we can verify:
  - the HTML scaffolding the JS depends on is present (search input,
    level-filter root, theme button, TOC toggle/panel, badge spans);
  - the JS bundle contains the function names that hook into that
    scaffolding (so a refactor that drops one of them surfaces here);
  - JS syntax validates via `node --check` if Node.js is available
    (this catches typos in the inline bundle without spinning up a real
    browser); skipped otherwise.
"""
from __future__ import annotations

import re
import shutil
import subprocess

import pytest

from runscroll import Collector


def _render(tmp_path):
    p = tmp_path / "x.html"
    with Collector(p, title="JS scaffold") as c:
        c.add_text("info entry")
        c.add_text("warning entry", level="warning")
        c.add_text("error entry", level="error")
        with c.section("S1"):
            c.add_text("inside s1")
            with c.section("S1.1"):
                c.add_text("inside s1.1")
        with c.section("S2"):
            c.add_text("inside s2")
    return p.read_text()


# ---------------------------------------------------------------------------
# HTML scaffolding the JS hooks into
# ---------------------------------------------------------------------------

def test_search_input_present(tmp_path):
    html_str = _render(tmp_path)
    assert re.search(r'<input[^>]*\bclass="rs-search"', html_str)


def test_level_filter_root_present(tmp_path):
    html_str = _render(tmp_path)
    assert re.search(r'class="rs-level-filter"', html_str)


def test_theme_toggle_present(tmp_path):
    html_str = _render(tmp_path)
    assert re.search(r'class="rs-theme-toggle"', html_str)


def test_toc_toggle_and_panel_present(tmp_path):
    html_str = _render(tmp_path)
    assert re.search(r'class="rs-toc-toggle"', html_str)
    assert re.search(r'class="rs-toc-panel"', html_str)
    assert re.search(r'class="rs-toc-nav"', html_str)


def test_badge_spans_present_for_error_and_warning(tmp_path):
    html_str = _render(tmp_path)
    assert 'data-rs-count="error"' in html_str
    assert 'data-rs-count="warning"' in html_str


def test_sections_have_id_and_data_attrs_for_toc(tmp_path):
    html_str = _render(tmp_path)
    # Three sections expected (S1, S1.1, S2).
    matches = re.findall(
        r'<section[^>]*data-rs-section-id="(\d+)"[^>]*data-rs-section-name="([^"]+)"',
        html_str,
    )
    assert len(matches) == 3
    ids = [int(m[0]) for m in matches]
    assert ids == [1, 2, 3]


# ---------------------------------------------------------------------------
# JS contains the expected hooks (string match against the inlined bundle)
# ---------------------------------------------------------------------------

def test_js_contains_expected_functions(tmp_path):
    html_str = _render(tmp_path)
    m = re.search(r"<script>(.*?)</script>", html_str, flags=re.DOTALL)
    assert m
    js = m.group(1)
    for name in (
        "buildLevelFilter",
        "bindLevelFilter",
        "buildToc",
        "bindSearch",
        "applySearch",
        "bindTheme",
        "updateBadges",
    ):
        assert name in js, f"expected function {name!r} in inlined JS"


def test_level_array_has_all_five_levels(tmp_path):
    html_str = _render(tmp_path)
    m = re.search(r"<script>(.*?)</script>", html_str, flags=re.DOTALL)
    js = m.group(1)
    for level in ("info", "debug", "warning", "error", "success"):
        assert f"'{level}'" in js


# ---------------------------------------------------------------------------
# Optional: JS syntax check via Node, when available
# ---------------------------------------------------------------------------

def test_js_syntax_validates_with_node_if_available(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available; skipping JS syntax check")

    html_str = _render(tmp_path)
    m = re.search(r"<script>(.*?)</script>", html_str, flags=re.DOTALL)
    js = m.group(1)
    js_path = tmp_path / "bundle.js"
    js_path.write_text(js, encoding="utf-8")

    result = subprocess.run(
        [node, "--check", str(js_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"node --check rejected the inlined JS:\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# Self-containment still holds after Step 9
# ---------------------------------------------------------------------------

def test_no_external_refs_after_step9(tmp_path):
    html_str = _render(tmp_path)
    # Step 9 emits no plotly or other heavy bundles, so we can do the
    # attribute check directly on the raw HTML — there are no <script>
    # / <style> bodies that contain incidental URL strings.
    pattern = re.compile(
        r'(?:src|href|srcset|cite|action|data-src)\s*=\s*["\']https?://',
        re.IGNORECASE,
    )
    assert pattern.search(html_str) is None
    # Inline <style> block must not @import or url() remote resources.
    style = re.search(r"<style>(.*?)</style>", html_str, flags=re.DOTALL).group(1)
    assert re.search(r"@import\s+(?:url\()?\s*['\"]?https?://", style) is None
    assert re.search(r"\burl\(\s*['\"]?https?://", style) is None
    # Step 9 doesn't introduce any <link href> or <script src> at all.
    assert re.search(r"<link\b[^>]*\bhref=", html_str) is None
    assert re.search(r"<script\b[^>]*\bsrc=", html_str) is None
