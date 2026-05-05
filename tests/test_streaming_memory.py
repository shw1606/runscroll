"""Memory safety gate (handoff §5, build-plan Step 3).

The single most important contract: Collector's RAM footprint must be O(1)
in the size of the report. These tests fail loudly if anyone introduces an
in-memory entry buffer or otherwise pins payloads after ``add_*`` returns.

Methodology
-----------
We use ``tracemalloc`` to measure Python-level allocations. RSS is too noisy
across platforms and CI runners — tracemalloc is deterministic, stdlib, and
attributable. ``gc.collect()`` is called between phases to remove cycles
from the picture.

Tolerances are expressed as **multiples of the input payload**, not absolute
bytes, so the tests survive interpreter and tracemalloc overhead variation.
"""
from __future__ import annotations

import gc
import tracemalloc

import pytest

from runscroll import Collector


def _current_bytes() -> int:
    """Return tracemalloc's current allocation count, in bytes."""
    return tracemalloc.get_traced_memory()[0]


@pytest.fixture
def trace():
    """Start tracemalloc fresh for each test, stop on teardown."""
    gc.collect()
    tracemalloc.start()
    try:
        yield
    finally:
        tracemalloc.stop()
        gc.collect()


# ---------------------------------------------------------------------------
# Case A — many small adds: residual must stay ~constant.
# ---------------------------------------------------------------------------

def test_many_small_adds_do_not_accumulate(tmp_path, trace):
    c = Collector(tmp_path / "x.html")
    gc.collect()
    baseline = _current_bytes()

    for i in range(1000):
        c.add_text(f"entry number {i}")
    gc.collect()

    after = _current_bytes()
    growth = after - baseline
    # Generous bound: ~200 KiB for 1000 adds. A real in-memory buffer would
    # easily exceed this (each entry's HTML is ~80 bytes -> 80 KB minimum,
    # plus list overhead + dict wrappers would push it well over).
    # We pick 256 KiB as a hard ceiling that's still tight enough to catch
    # accumulation (~256 bytes/entry residual would trip it).
    assert growth < 256 * 1024, (
        f"1000 small adds accumulated {growth/1024:.1f} KiB; "
        "Collector likely retaining entries in memory"
    )
    c.save()


# ---------------------------------------------------------------------------
# Case B — single large payload: must be released after add_text returns.
# ---------------------------------------------------------------------------

def test_large_payload_releases_after_add(tmp_path, trace):
    c = Collector(tmp_path / "x.html")
    gc.collect()
    baseline = _current_bytes()

    payload_bytes = 20 * 1024 * 1024  # 20 MiB
    payload = "x" * payload_bytes
    c.add_text(payload)
    del payload
    gc.collect()

    after = _current_bytes()
    growth = after - baseline
    # After the caller drops their reference and gc runs, the Collector
    # should hold none of the payload. Allow 1/10 of payload as slack
    # (file buffers, counters, etc.).
    assert growth < payload_bytes // 10, (
        f"20 MiB payload left {growth/1024/1024:.2f} MiB resident; "
        "Collector is pinning the input"
    )
    c.save()


# ---------------------------------------------------------------------------
# Case C — repeated large payloads: residual must NOT scale with N.
# ---------------------------------------------------------------------------

def test_repeated_large_payloads_do_not_accumulate(tmp_path, trace):
    c = Collector(tmp_path / "x.html")
    gc.collect()
    baseline = _current_bytes()

    payload_bytes = 10 * 1024 * 1024  # 10 MiB
    iterations = 30
    for _ in range(iterations):
        payload = "x" * payload_bytes
        c.add_text(payload)
        del payload
        gc.collect()

    after = _current_bytes()
    growth = after - baseline
    # Linear accumulation would be 30 * 10 MiB = 300 MiB. Anything close to
    # that means the Collector is accumulating. We bound at 1/30 of total
    # written volume (i.e., one payload's worth of slack), which catches
    # accumulation factors as small as ~1.1x.
    total_written = iterations * payload_bytes
    assert growth < total_written // 30, (
        f"{iterations}x{payload_bytes//1024//1024} MiB writes left "
        f"{growth/1024/1024:.2f} MiB resident; Collector is accumulating"
    )
    c.save()


# ---------------------------------------------------------------------------
# Case D — Collector instance state stays tiny regardless of work done.
# ---------------------------------------------------------------------------

def test_collector_instance_dict_stays_small(tmp_path):
    """Defense in depth: even without tracemalloc, the Collector's __dict__
    must not grow with the number of entries added.

    Snapshots are by *length* (not reference), since shared list refs would
    appear identical pre- and post-add otherwise.
    """

    def _container_lengths(obj):
        return {
            k: len(v)
            for k, v in obj.__dict__.items()
            if isinstance(v, (list, tuple, set, dict))
        }

    c = Collector(tmp_path / "x.html")
    keys_before = set(c.__dict__.keys())
    lengths_before = _container_lengths(c)

    for i in range(500):
        c.add_text(f"entry {i}")

    # No new attributes appeared.
    assert set(c.__dict__.keys()) == keys_before
    # No container attribute grew.
    lengths_after = _container_lengths(c)
    for key, length_after in lengths_after.items():
        assert length_after <= lengths_before.get(key, 0), (
            f"Collector grew container attribute {key!r}: "
            f"{lengths_before.get(key, 0)} -> {length_after}"
        )
    c.save()
