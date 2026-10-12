from pathlib import Path

import pandas as pd

from qrbt.engine.data.market import MarketData


class SnapshotRef:
    """Frozen. Location of a written snapshot: <root>/<sha256>.parquet and .json."""

    sha256: str
    parquet_path: Path
    manifest_path: Path

    def __init__(self, sha256: str, parquet_path: Path, manifest_path: Path) -> None:
        raise NotImplementedError


def write_snapshot(root: Path, close: pd.DataFrame, *, source: str, calendar: str) -> SnapshotRef:
    raise NotImplementedError


def load_snapshot(root: Path, sha256: str) -> MarketData:
    raise NotImplementedError
