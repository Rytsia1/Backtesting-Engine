import pandas as pd

from qrbt.engine.data.snapshot import _canonical
from qrbt.engine.errors import DataValidationError


def normalize_yfinance_frame(raw: pd.DataFrame) -> pd.DataFrame:
    """yfinance (Price, Ticker) MultiIndex frame -> canonical close frame.

    Reshape only: keeps Close, sorts tickers, float64, datetime64[ns] index named "date".
    NaN, timezones and empty frames pass through unchanged; validation happens downstream
    (write_snapshot, MarketData). Any other column layout raises DataValidationError.
    """
    columns = raw.columns
    if not isinstance(columns, pd.MultiIndex) or list(columns.names) != ["Price", "Ticker"]:
        raise DataValidationError(
            f"expected yfinance columns with levels ['Price', 'Ticker'], got {list(columns.names)}"
        )
    if "Close" not in columns.get_level_values("Price"):
        raise DataValidationError("yfinance frame has no Close column")
    return _canonical(pd.DataFrame(raw.xs("Close", axis=1, level="Price")))
