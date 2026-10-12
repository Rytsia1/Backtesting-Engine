import pandas as pd

from qrbt.engine.data import normalize_yfinance_frame

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
