"""AssetWriter protocol — pluggable asset destinations for directory mode.

Per handoff §7.1, the runscroll library is **infrastructure-agnostic**: it
knows how to compute and emit assets, but never how to authenticate to GCS,
S3, Azure, or whatever. The user supplies an ``AssetWriter`` that knows how
to put bytes at a relative path inside their target — local disk, cloud
bucket, sftp, doesn't matter.

The default ``LocalAssetWriter`` writes under a root directory and is what
``Collector(mode="directory")`` falls back to when no writer is supplied.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional, Protocol, Union, runtime_checkable


@runtime_checkable
class AssetWriter(Protocol):
    """Minimal contract: place ``content`` at ``relative_path``.

    Implementations should treat ``relative_path`` as opaque (the library
    composes it with ``assets/NNNN.ext``). They should be idempotent: if
    the same relative path is written twice, the last write wins.
    """

    def write(self, relative_path: str, content: bytes) -> None: ...


class LocalAssetWriter:
    """Default implementation: write under ``root/`` on the local disk.

    Has an extra ``write_from_path`` helper used by ``Collector`` when the
    user passes a path-based image source — that lets us stream-copy from
    one disk location to another without ever loading the full image into
    memory. The base ``AssetWriter`` protocol is intentionally bytes-only
    so third-party (e.g. S3) implementations stay simple; the local fast
    path is opt-in via duck-typing.
    """

    _COPY_CHUNK = 64 * 1024  # 64 KiB

    def __init__(self, root: Union[str, Path]) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def write(self, relative_path: str, content: bytes) -> None:
        target = self.root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)

    def write_from_path(self, relative_path: str, source: Path) -> None:
        target = self.root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        # shutil.copyfile streams in OS-page chunks internally.
        shutil.copyfile(source, target)
