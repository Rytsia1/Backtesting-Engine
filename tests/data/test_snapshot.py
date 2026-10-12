import hashlib
import json
import os
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, NoReturn

import numpy as np
import pandas as pd
import pytest

from qrbt.engine.data import MarketData, load_snapshot, validate_prices, write_snapshot
from qrbt.engine.errors import DataValidationError

DATES = ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-08"]
SOURCE = "synthetic"
CALENDAR = "XNYS"


def clean_close(unit: Literal["s", "ms", "us", "ns"] = "ns") -> pd.DataFrame:
    index = pd.DatetimeIndex(DATES, name="date").as_unit(unit)
    return pd.DataFrame(
        {
            "AAA": [100.0, 101.0, 102.0, 101.5, 103.0],
            "BBB": [50.0, 50.5, 49.8, 50.2, 51.0],
        },
        index=index,
        dtype="float64",
    )


def files_in(root: Path) -> set[str]:
    return {p.name for p in root.iterdir()}


def flip_one_byte(path: Path) -> bytes:
    data = bytearray(path.read_bytes())
    data[len(data) // 2] ^= 0xFF
    path.write_bytes(bytes(data))
    return bytes(data)


def test_write_then_load_roundtrip_is_identical(tmp_path: Path) -> None:
    close = clean_close()
    ref = write_snapshot(tmp_path, close, source=SOURCE, calendar=CALENDAR)
    md = load_snapshot(tmp_path, ref.sha256)
    pd.testing.assert_frame_equal(md.close, close)
    assert md.dataset_hash == ref.sha256
    assert md.calendar == CALENDAR
    assert md.open is None


def test_file_name_is_sha256_of_parquet_bytes(tmp_path: Path) -> None:
    ref = write_snapshot(tmp_path, clean_close(), source=SOURCE, calendar=CALENDAR)
    digest = hashlib.sha256(ref.parquet_path.read_bytes()).hexdigest()
    assert ref.sha256 == digest
    assert ref.parquet_path == tmp_path / f"{digest}.parquet"
    assert ref.manifest_path == tmp_path / f"{digest}.json"


def test_manifest_contents(tmp_path: Path) -> None:
    close = clean_close()
    close.iloc[2, 0] = 160.0  # +58% jump, so the report carries a warning
    ref = write_snapshot(tmp_path, close, source=SOURCE, calendar=CALENDAR)
    manifest = json.loads(ref.manifest_path.read_text(encoding="utf-8"))
    assert manifest["source"] == SOURCE
    assert manifest["tickers"] == ["AAA", "BBB"]
    assert manifest["calendar"] == CALENDAR
    assert manifest["start"] == "2024-01-02"
    assert manifest["end"] == "2024-01-08"
    assert manifest["validation"] == validate_prices(close).to_dict()
    assert datetime.fromisoformat(manifest["created_at"]).tzinfo is not None


def test_flipped_byte_makes_load_fail(tmp_path: Path) -> None:
    ref = write_snapshot(tmp_path, clean_close(), source=SOURCE, calendar=CALENDAR)
    flip_one_byte(ref.parquet_path)
    with pytest.raises(DataValidationError):
        load_snapshot(tmp_path, ref.sha256)


def test_writing_same_data_twice_is_idempotent(tmp_path: Path) -> None:
    first = write_snapshot(tmp_path, clean_close(), source=SOURCE, calendar=CALENDAR)
    parquet_bytes = first.parquet_path.read_bytes()
    manifest_bytes = first.manifest_path.read_bytes()
    second = write_snapshot(tmp_path, clean_close(), source=SOURCE, calendar=CALENDAR)
    assert second.sha256 == first.sha256
    assert second.parquet_path == first.parquet_path
    assert second.manifest_path == first.manifest_path
    assert files_in(tmp_path) == {first.parquet_path.name, first.manifest_path.name}
    assert first.parquet_path.read_bytes() == parquet_bytes
    assert first.manifest_path.read_bytes() == manifest_bytes


def test_existing_target_with_wrong_hash_raises(tmp_path: Path) -> None:
    ref = write_snapshot(tmp_path, clean_close(), source=SOURCE, calendar=CALENDAR)
    corrupted = flip_one_byte(ref.parquet_path)
    with pytest.raises(DataValidationError):
        write_snapshot(tmp_path, clean_close(), source=SOURCE, calendar=CALENDAR)
    assert files_in(tmp_path) == {ref.parquet_path.name, ref.manifest_path.name}
    assert ref.parquet_path.read_bytes() == corrupted


def test_failed_rename_leaves_no_temp_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    renamed_from: list[Path] = []

    def failing_replace(src: object, dst: object) -> NoReturn:
        # Fails after the temp file is on disk, i.e. at the final atomic rename.
        renamed_from.append(Path(str(src)))
        assert renamed_from[-1].is_file()
        raise OSError("injected failure in os.replace")

    monkeypatch.setattr(os, "replace", failing_replace)
    with pytest.raises(OSError, match="injected failure"):
        write_snapshot(tmp_path, clean_close(), source=SOURCE, calendar=CALENDAR)
    assert renamed_from, "write_snapshot never reached os.replace"
    assert files_in(tmp_path) == set()


def test_missing_manifest_is_rewritten_without_touching_parquet(tmp_path: Path) -> None:
    ref = write_snapshot(tmp_path, clean_close(), source=SOURCE, calendar=CALENDAR)
    parquet_bytes = ref.parquet_path.read_bytes()
    parquet_mtime = ref.parquet_path.stat().st_mtime_ns
    ref.manifest_path.unlink()
    again = write_snapshot(tmp_path, clean_close(), source=SOURCE, calendar=CALENDAR)
    assert again.sha256 == ref.sha256
    assert files_in(tmp_path) == {ref.parquet_path.name, ref.manifest_path.name}
    manifest = json.loads(ref.manifest_path.read_text(encoding="utf-8"))
    assert manifest["tickers"] == ["AAA", "BBB"]
    assert ref.parquet_path.read_bytes() == parquet_bytes
    assert ref.parquet_path.stat().st_mtime_ns == parquet_mtime


def test_injected_created_at_is_written_verbatim(tmp_path: Path) -> None:
    created_at = datetime(2024, 1, 9, 17, 30, 5, 123456, tzinfo=UTC)
    ref = write_snapshot(
        tmp_path, clean_close(), source=SOURCE, calendar=CALENDAR, created_at=created_at
    )
    manifest = json.loads(ref.manifest_path.read_text(encoding="utf-8"))
    assert manifest["created_at"] == "2024-01-09T17:30:05.123456+00:00"
    assert datetime.fromisoformat(manifest["created_at"]) == created_at


def test_invalid_data_cannot_be_written(tmp_path: Path) -> None:
    close = clean_close()
    close.iloc[1, 0] = -1.0
    with pytest.raises(DataValidationError):
        write_snapshot(tmp_path, close, source=SOURCE, calendar=CALENDAR)
    assert files_in(tmp_path) == set()


def test_second_and_nanosecond_index_give_same_hash(tmp_path: Path) -> None:
    (tmp_path / "s").mkdir()
    (tmp_path / "ns").mkdir()
    ref_s = write_snapshot(tmp_path / "s", clean_close("s"), source=SOURCE, calendar=CALENDAR)
    ref_ns = write_snapshot(tmp_path / "ns", clean_close("ns"), source=SOURCE, calendar=CALENDAR)
    assert ref_s.sha256 == ref_ns.sha256


def test_written_frame_is_canonicalized(tmp_path: Path) -> None:
    raw = pd.DataFrame(
        {"MSFT": [400, 401, 402], "AAPL": [190, 191, 189]},
        index=pd.DatetimeIndex(DATES[:3], name="Date").as_unit("s"),
    )
    ref = write_snapshot(tmp_path, raw, source=SOURCE, calendar=CALENDAR)
    md = load_snapshot(tmp_path, ref.sha256)
    expected = pd.DataFrame(
        {"AAPL": [190.0, 191.0, 189.0], "MSFT": [400.0, 401.0, 402.0]},
        index=pd.DatetimeIndex(DATES[:3], name="date").as_unit("ns"),
    )
    pd.testing.assert_frame_equal(md.close, expected)
    assert md.close.index.dtype == np.dtype("datetime64[ns]")
    assert isinstance(md.close.index, pd.DatetimeIndex)
    assert md.close.index.tz is None
    assert all(dtype == np.float64 for dtype in md.close.dtypes)


def test_market_data_is_frozen() -> None:
    md = MarketData(close=clean_close(), dataset_hash="0" * 64, calendar=CALENDAR)
    with pytest.raises(FrozenInstanceError):
        setattr(md, "calendar", "XIDX")  # noqa: B010


def test_market_data_open_is_optional() -> None:
    close = clean_close()
    without_open = MarketData(close=close, dataset_hash="0" * 64, calendar=CALENDAR)
    assert without_open.open is None
    with_open = MarketData(close=close, dataset_hash="0" * 64, calendar=CALENDAR, open=close)
    assert with_open.open is close
