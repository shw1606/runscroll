"""Tests for stdlib-only adapters: add_kv, add_code, add_table."""
from __future__ import annotations

import re

import pytest

from runscroll import Collector


def _between_main(html_str: str) -> str:
    """Return the body content between <main> and </main> for content-only checks."""
    m = re.search(r"<main[^>]*>(.*)</main>", html_str, flags=re.DOTALL)
    assert m is not None
    return m.group(1)


# ---------------------------------------------------------------------------
# add_kv
# ---------------------------------------------------------------------------

def test_add_kv_renders_two_column_table(tmp_path):
    p = tmp_path / "x.html"
    c = Collector(p)
    c.add_kv({"model": "resnet50", "lr": 3e-4, "bs": 64})
    c.save()

    body = _between_main(p.read_text())
    assert "rs-kv" in body
    assert "<th>model</th>" in body
    assert "<td>resnet50</td>" in body
    assert "<th>lr</th>" in body
    # 3e-4 stringifies to "0.0003"
    assert "<td>0.0003</td>" in body


def test_add_kv_with_title(tmp_path):
    p = tmp_path / "x.html"
    c = Collector(p)
    c.add_kv({"a": 1}, title="Hyperparams")
    c.save()
    body = _between_main(p.read_text())
    assert "rs-kv-title" in body
    assert "Hyperparams" in body


def test_add_kv_escapes_html(tmp_path):
    p = tmp_path / "x.html"
    c = Collector(p)
    c.add_kv({"<key>": "<value>"})
    c.save()
    body = _between_main(p.read_text())
    assert "<key>" not in body
    assert "<value>" not in body
    assert "&lt;key&gt;" in body
    assert "&lt;value&gt;" in body


def test_add_kv_empty_dict(tmp_path):
    """An empty dict should render an empty kv block, not crash."""
    p = tmp_path / "x.html"
    c = Collector(p)
    c.add_kv({})
    c.save()
    body = _between_main(p.read_text())
    assert "rs-kv" in body


# ---------------------------------------------------------------------------
# add_code
# ---------------------------------------------------------------------------

def test_add_code_renders_pre_code_block(tmp_path):
    p = tmp_path / "x.html"
    c = Collector(p)
    c.add_code("print('hi')", lang="python", title="example")
    c.save()
    body = _between_main(p.read_text())
    assert "rs-code" in body
    assert "<pre" in body
    assert "<code>" in body
    assert "print(&#x27;hi&#x27;)" in body  # html.escape escapes single quotes
    assert 'data-rs-lang="python"' in body
    assert "example" in body


def test_add_code_no_lang_no_data_attr(tmp_path):
    p = tmp_path / "x.html"
    c = Collector(p)
    c.add_code("x = 1")
    c.save()
    body = _between_main(p.read_text())
    assert "data-rs-lang" not in body


def test_add_code_escapes_dangerous_html(tmp_path):
    p = tmp_path / "x.html"
    c = Collector(p)
    c.add_code("<script>bad()</script>")
    c.save()
    body = _between_main(p.read_text())
    assert "<script>bad()</script>" not in body
    assert "&lt;script&gt;bad()&lt;/script&gt;" in body


# ---------------------------------------------------------------------------
# add_table — list of dicts
# ---------------------------------------------------------------------------

def test_add_table_list_of_dicts_uses_keys_as_columns(tmp_path):
    p = tmp_path / "x.html"
    c = Collector(p)
    c.add_table(
        [
            {"name": "a", "score": 1},
            {"name": "b", "score": 2, "extra": "z"},
        ],
        title="Per-class metrics",
    )
    c.save()
    body = _between_main(p.read_text())

    assert "Per-class metrics" in body
    # Headers in insertion order across rows: name, score, extra.
    headers_html = re.search(r"<thead>.*?</thead>", body, flags=re.DOTALL).group(0)
    name_pos = headers_html.index("<th>name</th>")
    score_pos = headers_html.index("<th>score</th>")
    extra_pos = headers_html.index("<th>extra</th>")
    assert name_pos < score_pos < extra_pos
    # Missing keys render as empty cells.
    assert "<td>a</td><td>1</td><td></td>" in body or "<td></td>" in body
    # Both data rows present.
    assert "<td>a</td>" in body and "<td>b</td>" in body


# ---------------------------------------------------------------------------
# add_table — list of lists
# ---------------------------------------------------------------------------

def test_add_table_list_of_lists_no_thead(tmp_path):
    p = tmp_path / "x.html"
    c = Collector(p)
    c.add_table([[1, 2, 3], [4, 5, 6]])
    c.save()
    body = _between_main(p.read_text())
    assert "<thead>" not in body
    for v in (1, 2, 3, 4, 5, 6):
        assert f"<td>{v}</td>" in body


def test_add_table_list_of_tuples_works(tmp_path):
    p = tmp_path / "x.html"
    c = Collector(p)
    c.add_table([("a", 1), ("b", 2)])
    c.save()
    body = _between_main(p.read_text())
    assert "<td>a</td>" in body
    assert "<td>2</td>" in body


# ---------------------------------------------------------------------------
# add_table — error handling
# ---------------------------------------------------------------------------

def test_add_table_empty_list(tmp_path):
    p = tmp_path / "x.html"
    c = Collector(p)
    c.add_table([])
    c.save()
    # Should produce a (possibly empty) rs-table block but not crash.
    assert "rs-table" in p.read_text()


def test_add_table_invalid_top_type(tmp_path):
    c = Collector(tmp_path / "x.html")
    with pytest.raises(TypeError):
        c.add_table({"not": "a list"})  # type: ignore[arg-type]
    c.save()


def test_add_table_mixed_row_types(tmp_path):
    c = Collector(tmp_path / "x.html")
    with pytest.raises(TypeError):
        c.add_table([{"a": 1}, [2, 3]])
    c.save()


def test_add_table_unknown_row_element_type(tmp_path):
    c = Collector(tmp_path / "x.html")
    with pytest.raises(TypeError):
        c.add_table([42, 43])
    c.save()


# ---------------------------------------------------------------------------
# All three feed through the same streaming contract.
# ---------------------------------------------------------------------------

def test_all_three_grow_file_immediately(tmp_path):
    p = tmp_path / "x.html"
    c = Collector(p)
    s0 = p.stat().st_size
    c.add_kv({"k": "v"})
    s1 = p.stat().st_size
    c.add_code("ok")
    s2 = p.stat().st_size
    c.add_table([[1, 2]])
    s3 = p.stat().st_size
    assert s0 < s1 < s2 < s3
    c.save()
