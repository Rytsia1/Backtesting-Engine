"""Content-addressed price snapshots: <root>/<sha256>.parquet plus <root>/<sha256>.json.

dataset_hash = SHA-256 of the canonical Parquet file bytes. Those bytes embed the pyarrow and
pandas versions, so the hash is reproducible for the versions pinned in uv.lock.
"""

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qrbt.engine.data.market import MarketData, _check_prices
from qrbt.engine.data.validation import ValidationReport, validate_prices
from qrbt.engine.errors import ConfigError, DataValidationError

_SHA256 = re.compile(r"[0-9a-f]{64}")
_MANIFEST_KEYS = frozenset(
    {"source", "tickers", "calendar", "start", "end", "validation", "created_at"}
)


@dataclass(frozen=True)
class SnapshotRef:
    """Location of a written snapshot."""

    sha256: str
    parquet_path: Path
    manifest_path: Path


def _canonical(close: pd.DataFrame) -> pd.DataFrame:
    """Sorted tickers, float64, tz-naive datetime64[ns] index named "date", no columns name."""
    out = close.sort_index(axis=1).astype(np.float64)
    out.index = pd.DatetimeIndex(out.index).as_unit("ns")
    return out.rename_axis(index="date", columns=None)


def _file_sha256(path: Path) -> str:
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def _temp_path(root: Path) -> Path:
    # Same directory as the target, so os.replace is an atomic rename.
    fd, name = tempfile.mkstemp(dir=root, suffix=".tmp")
    os.close(fd)
    return Path(name)


def _read_manifest(path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise DataValidationError(f"manifest {path.name} is not valid JSON: {e}") from e
    if not isinstance(manifest, dict):
        raise DataValidationError(f"manifest {path.name} is not a JSON object")
    missing = _MANIFEST_KEYS - manifest.keys()
    if missing:
        raise DataValidationError(f"manifest {path.name} is missing keys {sorted(missing)}")
    if not isinstance(manifest["calendar"], str):
        raise DataValidationError(f"manifest {path.name} has a non-string calendar")
    return manifest


def _check_manifest_matches(manifest: dict[str, Any], report: ValidationReport, name: str) -> None:
    expected = {"tickers": list(report.tickers), "start": report.start, "end": report.end}
    for key, value in expected.items():
        if manifest[key] != value:
            raise DataValidationError(
                f"manifest {name} {key}={manifest[key]!r} does not match the data ({value!r})"
            )


def write_snapshot(
    root: Path,
    close: pd.DataFrame,
    *,
    source: str,
    calendar: str,
    created_at: datetime | None = None,
) -> SnapshotRef:
    """Validate, canonicalize and store `close`; never overwrites an existing file.

    The Parquet file is written first and the manifest last, so a snapshot without a manifest
    is incomplete: load_snapshot rejects it and writing the same data again completes it.
    Same data with a different source or calendar is a conflict (DataValidationError).
    created_at=None reads datetime.now(UTC) here, at the I/O boundary only.
    """
    if created_at is None:
        created_at = datetime.now(UTC)
    elif created_at.utcoffset() is None:
        raise ConfigError(f"created_at must be timezone-aware, got {created_at!r}")

    report = validate_prices(close)
    canonical = _canonical(close)
    _check_prices(canonical, "close")
    manifest = {
        "source": source,
        "tickers": list(report.tickers),
        "calendar": calendar,
        "start": report.start,
        "end": report.end,
        "validation": report.to_dict(),
        "created_at": created_at.isoformat(),
    }

    tmp = _temp_path(root)
    try:
        canonical.to_parquet(tmp, engine="pyarrow")
        sha256 = _file_sha256(tmp)
        parquet_path = root / f"{sha256}.parquet"
        if not parquet_path.exists():
            os.replace(tmp, parquet_path)
        elif _file_sha256(parquet_path) != sha256:
            raise DataValidationError(f"existing {parquet_path.name} does not match its name")
    finally:
        tmp.unlink(missing_ok=True)

    manifest_path = root / f"{sha256}.json"
    if manifest_path.exists():
        existing = _read_manifest(manifest_path)
        _check_manifest_matches(existing, report, manifest_path.name)
        for key in ("source", "calendar"):
            if existing[key] != manifest[key]:
                raise DataValidationError(
                    f"snapshot {sha256[:12]} already has {key}={existing[key]!r}, "
                    f"refusing {manifest[key]!r}"
                )
    else:
        text = json.dumps(manifest, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
        tmp = _temp_path(root)
        try:
            tmp.write_text(text, encoding="utf-8")
            os.replace(tmp, manifest_path)
        finally:
            tmp.unlink(missing_ok=True)

    return SnapshotRef(sha256=sha256, parquet_path=parquet_path, manifest_path=manifest_path)


def load_snapshot(root: Path, sha256: str) -> MarketData:
    """Load a complete snapshot, verifying the file hash and the manifest. Raises
    DataValidationError for a malformed sha256, a missing file, a hash mismatch, or a
    manifest that is invalid or does not match the data."""
    if not _SHA256.fullmatch(sha256):
        raise DataValidationError(f"sha256 must be 64 lowercase hex characters, got {sha256!r}")
    parquet_path = root / f"{sha256}.parquet"
    manifest_path = root / f"{sha256}.json"
    for path in (parquet_path, manifest_path):
        if not path.is_file():
            raise DataValidationError(f"snapshot file {path.name} is missing")
    if _file_sha256(parquet_path) != sha256:
        raise DataValidationError(f"{parquet_path.name} content does not match its hash")

    manifest = _read_manifest(manifest_path)
    md = MarketData(
        close=pd.read_parquet(parquet_path, engine="pyarrow"),
        dataset_hash=sha256,
        calendar=manifest["calendar"],
    )
    _check_manifest_matches(manifest, validate_prices(md.close), manifest_path.name)
    return md
