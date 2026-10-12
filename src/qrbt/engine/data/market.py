from dataclasses import dataclass

import numpy as np
import pandas as pd

from qrbt.engine.data.validation import validate_prices
from qrbt.engine.errors import DataValidationError


def _check_prices(frame: pd.DataFrame, name: str) -> None:
    """validate_prices plus the canonical form: float64, datetime64[ns], sorted unique tickers."""
    validate_prices(frame)
    if frame.index.dtype != np.dtype("datetime64[ns]"):
        raise DataValidationError(f"{name} index must be datetime64[ns], got {frame.index.dtype}")
    not_float = [str(c) for c, dtype in frame.dtypes.items() if dtype != np.float64]
    if not_float:
        raise DataValidationError(f"{name} columns must be float64, not: {not_float}")
    if not (frame.columns.is_unique and frame.columns.is_monotonic_increasing):
        raise DataValidationError(
            f"{name} tickers must be unique and sorted alphabetically, got {list(frame.columns)}"
        )


@dataclass(frozen=True, eq=False, init=False)
class MarketData:
    """Validated adjusted close prices plus their dataset identity.

    Frozen, and isolated from the caller: frames are copied in on construction and
    copied out on every access (both O(1) under pandas copy-on-write).
    """

    _close: pd.DataFrame
    dataset_hash: str
    calendar: str
    _open: pd.DataFrame | None

    def __init__(
        self,
        close: pd.DataFrame,
        dataset_hash: str,
        calendar: str,
        open: pd.DataFrame | None = None,
    ) -> None:
        _check_prices(close, "close")
        if open is not None:
            _check_prices(open, "open")
            # equals() ignores axis names, so compare them explicitly.
            if not (
                open.index.equals(close.index)
                and open.columns.equals(close.columns)
                and open.index.name == close.index.name
                and open.columns.name == close.columns.name
            ):
                raise DataValidationError(
                    "open must have the same index and columns (values and names) as close"
                )
        object.__setattr__(self, "_close", close.copy(deep=False))
        object.__setattr__(self, "dataset_hash", dataset_hash)
        object.__setattr__(self, "calendar", calendar)
        object.__setattr__(self, "_open", None if open is None else open.copy(deep=False))

    @property
    def close(self) -> pd.DataFrame:
        return self._close.copy(deep=False)

    @property
    def open(self) -> pd.DataFrame | None:
        return None if self._open is None else self._open.copy(deep=False)
