import numpy as np
import pandas as pd
import pytest

from qrbt.engine.data import normalize_yfinance_frame
from qrbt.engine.errors import DataValidationError

DATES = ["2024-01-02", "2024-01-03", "2024-01-04"]


def test_normalize_yfinance_frame_keeps_only_sorted_close() -> None:
    raw = pd.DataFrame(
        {
            ("Close", "MSFT"): [400.0, 401.0, 402.0],
            ("Close", "AAPL"): [190.0, 191.0, 189.0],
            ("High", "MSFT"): [405.0, 406.0, 407.0],
            ("High", "AAPL"): [195.0, 196.0, 194.0],
            ("Low", "MSFT"): [395.0, 396.0, 397.0],
            ("Low", "AAPL"): [185.0, 186.0, 184.0],
            ("Open", "MSFT"): [398.0, 400.0, 401.0],
            ("Open", "AAPL"): [188.0, 190.0, 191.0],
            ("Volume", "MSFT"): [1000, 1100, 1200],
            ("Volume", "AAPL"): [2000, 2100, 2200],
        },
        index=pd.DatetimeIndex(DATES, name="Date").as_unit("s"),
    )
    raw.columns = raw.columns.set_names(["Price", "Ticker"])

    result = normalize_yfinance_frame(raw)

    expected = pd.DataFrame(
        {"AAPL": [190.0, 191.0, 189.0], "MSFT": [400.0, 401.0, 402.0]},
        index=pd.DatetimeIndex(DATES, name="date").as_unit("ns"),
    )
    pd.testing.assert_frame_equal(result, expected)


def yf_frame(close_msft: list[float], index: pd.DatetimeIndex) -> pd.DataFrame:
    raw = pd.DataFrame(
        {("Close", "MSFT"): close_msft, ("Volume", "MSFT"): [1000] * len(close_msft)},
        index=index,
    )
    raw.columns = raw.columns.set_names(["Price", "Ticker"])
    return raw


def test_single_level_columns_are_rejected() -> None:
    raw = pd.DataFrame({"Close": [400.0, 401.0, 402.0]}, index=pd.DatetimeIndex(DATES))
    with pytest.raises(DataValidationError):
        normalize_yfinance_frame(raw)


def test_unexpected_level_names_are_rejected() -> None:
    raw = yf_frame([400.0, 401.0, 402.0], pd.DatetimeIndex(DATES))
    raw.columns = raw.columns.set_names(["Ticker", "Price"])  # group_by="ticker" layout
    with pytest.raises(DataValidationError):
        normalize_yfinance_frame(raw)


def test_frame_without_close_is_rejected() -> None:
    raw = yf_frame([400.0, 401.0, 402.0], pd.DatetimeIndex(DATES)).drop(columns="Close", level=0)
    with pytest.raises(DataValidationError):
        normalize_yfinance_frame(raw)


def test_nan_passes_through_unchanged() -> None:
    result = normalize_yfinance_frame(yf_frame([400.0, np.nan, 402.0], pd.DatetimeIndex(DATES)))
    assert len(result) == 3
    assert result["MSFT"].isna().tolist() == [False, True, False]


def test_timezone_passes_through_unchanged() -> None:
    index = pd.DatetimeIndex(DATES).tz_localize("America/New_York")
    result = normalize_yfinance_frame(yf_frame([400.0, 401.0, 402.0], index))
    result_index = result.index
    assert isinstance(result_index, pd.DatetimeIndex)
    assert str(result_index.tz) == "America/New_York"


def test_empty_frame_passes_through() -> None:
    result = normalize_yfinance_frame(yf_frame([], pd.DatetimeIndex([])))
    assert result.empty
    assert result.columns.tolist() == ["MSFT"]


@pytest.mark.parametrize(
    "values", [["400.0", "401.0", "402.0"], [True, True, True]], ids=["str", "bool"]
)
def test_non_numeric_close_is_rejected_not_converted(values: list[object]) -> None:
    raw = pd.DataFrame({("Close", "MSFT"): values}, index=pd.DatetimeIndex(DATES))
    raw.columns = raw.columns.set_names(["Price", "Ticker"])
    with pytest.raises(DataValidationError):
        normalize_yfinance_frame(raw)


def test_non_datetime_index_is_rejected_not_parsed() -> None:
    raw = pd.DataFrame({("Close", "MSFT"): [400.0, 401.0, 402.0]}, index=pd.Index(DATES))
    raw.columns = raw.columns.set_names(["Price", "Ticker"])
    with pytest.raises(DataValidationError):
        normalize_yfinance_frame(raw)
