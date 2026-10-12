import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from qrbt.engine.data import load_snapshot, write_snapshot
from qrbt.engine.errors import ConfigError, DataValidationError

DATES = ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-08"]
SOURCE = "synthetic"
CALENDAR = "XNYS"


def clean_close() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "AAA": [100.0, 101.0, 102.0, 101.5, 103.0],
            "BBB": [50.0, 50.5, 49.8, 50.2, 51.0],
        },
        index=pd.DatetimeIndex(DATES, name="date").as_unit("ns"),
    )


def files_in(root: Path) -> set[str]:
    return {p.name for p in root.iterdir()}


# --- load: missing, corrupt, or inconsistent files ---


def test_load_with_missing_parquet_raises(tmp_path: Path) -> None:
    ref = write_snapshot(tmp_path, clean_close(), source=SOURCE, calendar=CALENDAR)
    ref.parquet_path.unlink()
    with pytest.raises(DataValidationError):
        load_snapshot(tmp_path, ref.sha256)


def test_load_with_missing_manifest_raises(tmp_path: Path) -> None:
    ref = write_snapshot(tmp_path, clean_close(), source=SOURCE, calendar=CALENDAR)
    ref.manifest_path.unlink()
    with pytest.raises(DataValidationError):
        load_snapshot(tmp_path, ref.sha256)


def test_load_with_malformed_manifest_raises(tmp_path: Path) -> None:
    ref = write_snapshot(tmp_path, clean_close(), source=SOURCE, calendar=CALENDAR)
    ref.manifest_path.write_text("{not json", encoding="utf-8")
    with pytest.raises(DataValidationError):
        load_snapshot(tmp_path, ref.sha256)


@pytest.mark.parametrize(
    "key", ["source", "tickers", "calendar", "start", "end", "validation", "created_at"]
)
def test_load_with_manifest_missing_a_key_raises(tmp_path: Path, key: str) -> None:
    ref = write_snapshot(tmp_path, clean_close(), source=SOURCE, calendar=CALENDAR)
    manifest = json.loads(ref.manifest_path.read_text(encoding="utf-8"))
    del manifest[key]
    ref.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(DataValidationError):
        load_snapshot(tmp_path, ref.sha256)


@pytest.mark.parametrize(
    ("key", "value"),
    [("tickers", ["AAA", "CCC"]), ("start", "2024-01-03"), ("end", "2024-01-09")],
)
def test_load_with_manifest_not_matching_data_raises(
    tmp_path: Path, key: str, value: object
) -> None:
    ref = write_snapshot(tmp_path, clean_close(), source=SOURCE, calendar=CALENDAR)
    manifest = json.loads(ref.manifest_path.read_text(encoding="utf-8"))
    manifest[key] = value
    ref.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(DataValidationError):
        load_snapshot(tmp_path, ref.sha256)


@pytest.mark.parametrize("sha256", ["", "0" * 63, "0" * 65, "A" * 64, "g" * 64, "../" + "0" * 61])
def test_load_rejects_malformed_sha256(tmp_path: Path, sha256: str) -> None:
    with pytest.raises(DataValidationError):
        load_snapshot(tmp_path, sha256)


# --- write: conflicts, determinism, canonical form ---


@pytest.mark.parametrize("field", ["source", "calendar"])
def test_same_data_with_conflicting_metadata_is_rejected(tmp_path: Path, field: str) -> None:
    ref = write_snapshot(tmp_path, clean_close(), source=SOURCE, calendar=CALENDAR)
    parquet_bytes = ref.parquet_path.read_bytes()
    manifest_bytes = ref.manifest_path.read_bytes()
    source = "other" if field == "source" else SOURCE
    calendar = "XIDX" if field == "calendar" else CALENDAR
    with pytest.raises(DataValidationError):
        write_snapshot(tmp_path, clean_close(), source=source, calendar=calendar)
    assert files_in(tmp_path) == {ref.parquet_path.name, ref.manifest_path.name}
    assert ref.parquet_path.read_bytes() == parquet_bytes
    assert ref.manifest_path.read_bytes() == manifest_bytes


def test_different_data_gives_different_hash(tmp_path: Path) -> None:
    changed = clean_close()
    changed.iloc[3, 1] = 50.3
    a = write_snapshot(tmp_path, clean_close(), source=SOURCE, calendar=CALENDAR)
    b = write_snapshot(tmp_path, changed, source=SOURCE, calendar=CALENDAR)
    assert a.sha256 != b.sha256


def test_column_order_does_not_change_hash(tmp_path: Path) -> None:
    a = write_snapshot(tmp_path, clean_close(), source=SOURCE, calendar=CALENDAR)
    b = write_snapshot(tmp_path, clean_close()[["BBB", "AAA"]], source=SOURCE, calendar=CALENDAR)
    assert a.sha256 == b.sha256


def test_columns_axis_name_does_not_change_hash(tmp_path: Path) -> None:
    named = clean_close()
    named.columns.name = "Ticker"
    a = write_snapshot(tmp_path, clean_close(), source=SOURCE, calendar=CALENDAR)
    b = write_snapshot(tmp_path, named, source=SOURCE, calendar=CALENDAR)
    assert a.sha256 == b.sha256


def test_missing_root_is_not_created(tmp_path: Path) -> None:
    root = tmp_path / "missing"
    with pytest.raises(FileNotFoundError):
        write_snapshot(root, clean_close(), source=SOURCE, calendar=CALENDAR)
    assert not root.exists()


def test_naive_created_at_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        write_snapshot(
            tmp_path,
            clean_close(),
            source=SOURCE,
            calendar=CALENDAR,
            created_at=datetime(2024, 1, 9, 17, 30),
        )
    assert files_in(tmp_path) == set()


# --- partial writes ---


def test_crash_before_manifest_leaves_an_unloadable_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_replace = os.replace
    calls: list[str] = []

    def replace_then_crash(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        calls.append(str(dst))
        if len(calls) == 2:  # parquet goes first, the manifest second
            raise OSError("injected crash before manifest")
        real_replace(src, dst)

    with monkeypatch.context() as m:
        m.setattr(os, "replace", replace_then_crash)
        with pytest.raises(OSError, match="injected crash"):
            write_snapshot(tmp_path, clean_close(), source=SOURCE, calendar=CALENDAR)

    assert [Path(c).suffix for c in calls] == [".parquet", ".json"]
    (parquet,) = tmp_path.iterdir()  # no temp files, no manifest
    assert parquet.suffix == ".parquet"
    with pytest.raises(DataValidationError):
        load_snapshot(tmp_path, parquet.stem)

    ref = write_snapshot(tmp_path, clean_close(), source=SOURCE, calendar=CALENDAR)
    assert ref.sha256 == parquet.stem
    pd.testing.assert_frame_equal(load_snapshot(tmp_path, ref.sha256).close, clean_close())


# --- review follow-up: no silent type conversion, parse exactly the verified bytes ---


@pytest.mark.parametrize(
    "values", [["1.0", "2.0", "3.0", "4.0", "5.0"], [True] * 5], ids=["str", "bool"]
)
def test_non_numeric_prices_are_rejected_not_converted(
    tmp_path: Path, values: list[object]
) -> None:
    close = pd.DataFrame({"AAA": values}, index=pd.DatetimeIndex(DATES, name="date").as_unit("ns"))
    with pytest.raises(DataValidationError):
        write_snapshot(tmp_path, close, source=SOURCE, calendar=CALENDAR)
    assert files_in(tmp_path) == set()


def test_load_parses_exactly_the_bytes_it_verified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ref = write_snapshot(tmp_path, clean_close(), source=SOURCE, calendar=CALENDAR)
    other_root = tmp_path / "other"
    other_root.mkdir()
    swapped = clean_close()
    swapped.iloc[0, 0] = 99.0  # same tickers and dates, so the manifest would still match
    swapped_bytes = write_snapshot(
        other_root, swapped, source=SOURCE, calendar=CALENDAR
    ).parquet_path.read_bytes()
    real_read_parquet = pd.read_parquet

    def swap_file_then_read(path: Any, *args: Any, **kwargs: Any) -> pd.DataFrame:
        ref.parquet_path.write_bytes(swapped_bytes)  # the file changes after the hash check
        return real_read_parquet(path, *args, **kwargs)

    monkeypatch.setattr(pd, "read_parquet", swap_file_then_read)
    md = load_snapshot(tmp_path, ref.sha256)
    pd.testing.assert_frame_equal(md.close, clean_close())
