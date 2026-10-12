import builtins
import os
from pathlib import Path
from typing import NoReturn

import numpy as np
import pandas as pd
import pytest

from qrbt.engine.data import validate_prices
from qrbt.engine.errors import DataValidationError

DATES = ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-08"]


def make_close(values: dict[str, list[float]], dates: list[str] = DATES) -> pd.DataFrame:
    index = pd.DatetimeIndex(dates, name="date").as_unit("ns")
    return pd.DataFrame(values, index=index, dtype="float64")


def clean_close() -> pd.DataFrame:
    return make_close(
        {
            "AAA": [100.0, 101.0, 102.0, 101.5, 103.0],
            "BBB": [50.0, 50.5, 49.8, 50.2, 51.0],
        }
    )


def test_clean_data_passes_without_warnings() -> None:
    report = validate_prices(clean_close())
    assert report.n_rows == 5
    assert list(report.tickers) == ["AAA", "BBB"]
    assert report.start == "2024-01-02"
    assert report.end == "2024-01-08"
    assert list(report.warnings) == []


def test_nan_raises() -> None:
    close = clean_close()
    close.iloc[2, 0] = np.nan
    with pytest.raises(DataValidationError):
        validate_prices(close)


def test_duplicate_dates_raise() -> None:
    close = make_close({"AAA": [100.0, 101.0, 102.0]}, ["2024-01-02", "2024-01-03", "2024-01-03"])
    with pytest.raises(DataValidationError):
        validate_prices(close)


def test_unsorted_dates_raise() -> None:
    close = make_close({"AAA": [100.0, 101.0, 102.0]}, ["2024-01-02", "2024-01-04", "2024-01-03"])
    with pytest.raises(DataValidationError):
        validate_prices(close)


def test_zero_price_raises() -> None:
    close = clean_close()
    close.iloc[1, 1] = 0.0
    with pytest.raises(DataValidationError):
        validate_prices(close)


def test_negative_price_raises() -> None:
    close = clean_close()
    close.iloc[1, 1] = -1.0
    with pytest.raises(DataValidationError):
        validate_prices(close)


def test_timezone_aware_index_raises() -> None:
    close = clean_close()
    close.index = pd.DatetimeIndex(close.index).tz_localize("UTC")
    with pytest.raises(DataValidationError):
        validate_prices(close)


def test_empty_frame_raises() -> None:
    close = make_close({"AAA": []}, [])
    with pytest.raises(DataValidationError):
        validate_prices(close)


def test_daily_jump_above_threshold_is_warning_not_error() -> None:
    close = make_close(
        {
            "AAA": [100.0, 101.0, 160.0, 158.0, 159.0],
            "BBB": [50.0, 50.5, 49.8, 50.2, 51.0],
        }
    )
    report = validate_prices(close)
    assert len(report.warnings) == 1
    warning = report.warnings[0]
    assert warning.code == "extreme_return"
    assert warning.date == "2024-01-04"
    assert warning.ticker == "AAA"
    assert warning.value == pytest.approx(160.0 / 101.0 - 1.0)


def test_daily_drop_above_threshold_warns_with_negative_value() -> None:
    close = make_close(
        {
            "AAA": [100.0, 101.0, 40.4, 41.0, 41.5],  # 40.4 / 101.0 - 1 = -0.6
            "BBB": [50.0, 50.5, 49.8, 50.2, 51.0],
        }
    )
    report = validate_prices(close)
    assert len(report.warnings) == 1
    warning = report.warnings[0]
    assert warning.code == "extreme_return"
    assert warning.date == "2024-01-04"
    assert warning.ticker == "AAA"
    assert warning.value == pytest.approx(-0.6)
    assert warning.value < 0


def test_return_exactly_at_threshold_is_not_warning() -> None:
    # 100 -> 150 is exactly +0.5 in float64; the threshold is strict (> max_abs_return).
    close = make_close({"AAA": [100.0, 150.0, 151.0, 152.0, 153.0]})
    assert 150.0 / 100.0 - 1.0 == 0.5
    report = validate_prices(close, max_abs_return=0.5)
    assert list(report.warnings) == []


@pytest.mark.parametrize("bad", [np.inf, -np.inf])
def test_infinite_price_raises(bad: float) -> None:
    close = clean_close()
    close.iloc[2, 0] = bad
    with pytest.raises(DataValidationError):
        validate_prices(close)


def test_does_not_modify_input() -> None:
    close = clean_close()
    before = close.copy(deep=True)
    validate_prices(close)
    pd.testing.assert_frame_equal(close, before)


def test_does_not_touch_disk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("validate_prices touched the disk")

    close = clean_close()
    monkeypatch.chdir(tmp_path)
    with monkeypatch.context() as m:
        m.setattr(builtins, "open", forbidden)
        m.setattr(os, "open", forbidden)
        validate_prices(close)
    assert list(tmp_path.iterdir()) == []
