"""Serialization helpers for entry types.

Each ``render_*`` function returns a self-contained HTML string for one
entry. Per the streaming append-write contract (handoff §5), we never
build up an in-memory list of entry objects — the Collector calls
``render_*``, writes the result, and forgets it.

The functions are intentionally pure (input -> string), so they're easy
to test without touching the filesystem.
"""
from __future__ import annotations

import html
from typing import Any, List, Mapping, Sequence


def _escape(v: Any) -> str:
    return html.escape(str(v))


def render_kv(mapping: Mapping[str, Any], title: str = "") -> str:
    parts: List[str] = ['<div class="rs-entry rs-kv">']
    if title:
        parts.append(f'<div class="rs-kv-title">{_escape(title)}</div>')
    parts.append('<table class="rs-kv-table"><tbody>')
    for k, v in mapping.items():
        parts.append(
            f"<tr><th>{_escape(k)}</th><td>{_escape(v)}</td></tr>"
        )
    parts.append("</tbody></table></div>\n")
    return "".join(parts)


def render_code(code: str, lang: str = "", title: str = "") -> str:
    parts: List[str] = ['<div class="rs-entry rs-code">']
    if title:
        parts.append(f'<div class="rs-code-title">{_escape(title)}</div>')
    lang_attr = f' data-rs-lang="{_escape(lang)}"' if lang else ""
    parts.append(f"<pre{lang_attr}><code>{_escape(code)}</code></pre>")
    parts.append("</div>\n")
    return "".join(parts)


def render_table(data: Sequence[Any], title: str = "") -> str:
    """Render a list of dicts or a list of lists/tuples as an HTML table.

    - ``list[dict]`` -> columns are the union of keys (insertion order
      preserved across rows). Missing values render as empty strings.
    - ``list[list|tuple]`` -> rendered without a ``<thead>``; rows may be
      ragged (cells beyond the row are simply omitted, no padding).
    - empty list -> empty table.

    pandas DataFrames are intentionally not handled here; that's the
    pandas adapter's job (introduced in a later step) so the core stays
    stdlib-only.
    """
    if not isinstance(data, (list, tuple)):
        raise TypeError(
            f"add_table: data must be list[dict] or list[list]; got {type(data).__name__}"
        )

    parts: List[str] = ['<div class="rs-entry rs-table">']
    if title:
        parts.append(f'<div class="rs-table-title">{_escape(title)}</div>')

    if not data:
        parts.append('<table class="rs-data-table"><tbody></tbody></table>')
        parts.append("</div>\n")
        return "".join(parts)

    first = data[0]
    if isinstance(first, dict):
        cols: List[Any] = []
        seen = set()
        for row in data:
            if not isinstance(row, dict):
                raise TypeError(
                    "add_table: rows must be uniform; got mix of dict and "
                    f"{type(row).__name__}"
                )
            for k in row.keys():
                if k not in seen:
                    seen.add(k)
                    cols.append(k)
        parts.append('<table class="rs-data-table"><thead><tr>')
        for c in cols:
            parts.append(f"<th>{_escape(c)}</th>")
        parts.append("</tr></thead><tbody>")
        for row in data:
            parts.append("<tr>")
            for c in cols:
                parts.append(f"<td>{_escape(row.get(c, ''))}</td>")
            parts.append("</tr>")
        parts.append("</tbody></table>")
    elif isinstance(first, (list, tuple)):
        parts.append('<table class="rs-data-table"><tbody>')
        for row in data:
            if not isinstance(row, (list, tuple)):
                raise TypeError(
                    "add_table: rows must be uniform; got mix of list/tuple "
                    f"and {type(row).__name__}"
                )
            parts.append("<tr>")
            for cell in row:
                parts.append(f"<td>{_escape(cell)}</td>")
            parts.append("</tr>")
        parts.append("</tbody></table>")
    else:
        raise TypeError(
            "add_table: list elements must be dict or list/tuple; got "
            f"{type(first).__name__}"
        )

    parts.append("</div>\n")
    return "".join(parts)
