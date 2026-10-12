from typing import Literal

import numpy as np
import pandas as pd
import pytest

from qrbt.engine.data import MarketData
from qrbt.engine.errors import DataValidationError

DATES = ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-08"]
HASH = "0" * 64
CALENDAR = "XNYS"


def make_frame(
    values: dict[str, list[float]],
    *,
    dtype: Literal["float64", "float32", "int64"] = "float64",
    unit: Literal["s", "ms", "us", "ns"] = "ns",
) -> pd.DataFrame:
    index = pd.DatetimeIndex(DATES, name="date").as_unit(unit)
    return pd.DataFrame(values, index=index).astype(dtype)


def clean_close() -> pd.DataFrame:
    return make_frame(
        {
            "AAA": [100.0, 101.0, 102.0, 101.5, 103.0],
            "BBB": [50.0, 50.5, 49.8, 50.2, 51.0],
        }
    )


def clean_open() -> pd.DataFrame:
    return make_frame(
        {
            "AAA": [99.5, 100.5, 101.5, 102.0, 102.0],
            "BBB": [49.9, 50.1, 50.4, 49.9, 50.5],
        }
    )


# --- valid input ---


def test_valid_close_and_open_are_accepted() -> None:
    close, open_ = clean_close(), clean_open()
    md = MarketData(close=close, dataset_hash=HASH, calendar=CALENDAR, open=open_)
    pd.testing.assert_frame_equal(md.close, close)
    assert md.open is not None
    pd.testing.assert_frame_equal(md.open, open_)
    assert md.dataset_hash == HASH
    assert md.calendar == CALENDAR


# --- invalid close ---


@pytest.mark.parametrize("bad", [np.nan, np.inf, 0.0, -1.0])
def test_close_failing_validate_prices_is_rejected(bad: float) -> None:
    close = clean_close()
    close.iloc[2, 0] = bad
    with pytest.raises(DataValidationError):
        MarketData(close=close, dataset_hash=HASH, calendar=CALENDAR)


def test_unsorted_tickers_are_rejected() -> None:
    close = clean_close()[["BBB", "AAA"]]
    with pytest.raises(DataValidationError):
        MarketData(close=close, dataset_hash=HASH, calendar=CALENDAR)


def test_duplicate_tickers_are_rejected() -> None:
    close = clean_close()
    close.columns = pd.Index(["AAA", "AAA"])
    with pytest.raises(DataValidationError):
        MarketData(close=close, dataset_hash=HASH, calendar=CALENDAR)


@pytest.mark.parametrize("dtype", ["float32", "int64"])
def test_non_float64_close_is_rejected(dtype: Literal["float32", "int64"]) -> None:
    close = make_frame({"AAA": [100, 101, 102, 101, 103]}, dtype=dtype)
    with pytest.raises(DataValidationError):
        MarketData(close=close, dataset_hash=HASH, calendar=CALENDAR)


@pytest.mark.parametrize("unit", ["s", "ms", "us"])
def test_non_nanosecond_index_is_rejected(unit: Literal["s", "ms", "us"]) -> None:
    close = make_frame({"AAA": [100.0, 101.0, 102.0, 101.5, 103.0]}, unit=unit)
    with pytest.raises(DataValidationError):
        MarketData(close=close, dataset_hash=HASH, calendar=CALENDAR)


# --- invalid open ---


def test_open_with_different_index_is_rejected() -> None:
    open_ = clean_open()
    open_.index = pd.DatetimeIndex(
        ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-09"], name="date"
    ).as_unit("ns")
    with pytest.raises(DataValidationError):
        MarketData(close=clean_close(), dataset_hash=HASH, calendar=CALENDAR, open=open_)


def test_open_with_different_columns_is_rejected() -> None:
    open_ = clean_open()[["AAA"]]
    with pytest.raises(DataValidationError):
        MarketData(close=clean_close(), dataset_hash=HASH, calendar=CALENDAR, open=open_)


def test_open_with_same_dates_but_other_resolution_is_rejected() -> None:
    open_ = clean_open()
    # Same dates, so equals() the close index, but the resolution is [s] not [ns].
    open_.index = pd.DatetimeIndex(open_.index).as_unit("s")
    with pytest.raises(DataValidationError):
        MarketData(close=clean_close(), dataset_hash=HASH, calendar=CALENDAR, open=open_)


def test_open_with_different_index_name_is_rejected() -> None:
    open_ = clean_open()
    open_.index.name = "Date"  # same dates, different name
    with pytest.raises(DataValidationError):
        MarketData(close=clean_close(), dataset_hash=HASH, calendar=CALENDAR, open=open_)


def test_open_with_different_columns_name_is_rejected() -> None:
    open_ = clean_open()
    open_.columns.name = "Ticker"  # same tickers, different axis name
    with pytest.raises(DataValidationError):
        MarketData(close=clean_close(), dataset_hash=HASH, calendar=CALENDAR, open=open_)


def test_open_failing_validate_prices_is_rejected() -> None:
    open_ = clean_open()
    open_.iloc[1, 1] = np.nan
    with pytest.raises(DataValidationError):
        MarketData(close=clean_close(), dataset_hash=HASH, calendar=CALENDAR, open=open_)


# --- mutation protection ---


def test_mutating_source_after_construction_does_not_leak() -> None:
    close, open_ = clean_close(), clean_open()
    md = MarketData(close=close, dataset_hash=HASH, calendar=CALENDAR, open=open_)
    close.iloc[0, 0] = 999.0
    open_.iloc[0, 0] = 999.0
    close.index.name = "changed"
    assert md.close.iloc[0, 0] == 100.0
    assert md.close.index.name == "date"
    assert md.open is not None
    assert md.open.iloc[0, 0] == 99.5


def test_mutating_returned_frames_does_not_change_market_data() -> None:
    md = MarketData(close=clean_close(), dataset_hash=HASH, calendar=CALENDAR, open=clean_open())
    leaked_close = md.close
    leaked_close.iloc[0, 0] = 999.0
    leaked_close.index.name = "changed"
    leaked_close["CCC"] = 1.0
    leaked_open = md.open
    assert leaked_open is not None
    leaked_open.iloc[0, 0] = 999.0
    pd.testing.assert_frame_equal(md.close, clean_close())
    assert md.open is not None
    pd.testing.assert_frame_equal(md.open, clean_open())


def test_construction_does_not_modify_inputs() -> None:
    close, open_ = clean_close(), clean_open()
    MarketData(close=close, dataset_hash=HASH, calendar=CALENDAR, open=open_)
    pd.testing.assert_frame_equal(close, clean_close())
    pd.testing.assert_frame_equal(open_, clean_open())
