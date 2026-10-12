import math
import numbers
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from qrbt.engine.errors import ConfigError, DataValidationError

EXTREME_RETURN = "extreme_return"


@dataclass(frozen=True)
class ValidationWarning:
    """A non-fatal finding, e.g. an extreme daily return."""

    code: str
    date: str  # "YYYY-MM-DD"
    ticker: str
    value: float


@dataclass(frozen=True)
class ValidationReport:
    """Summary of a price frame that passed validation."""

    n_rows: int
    tickers: tuple[str, ...]
    start: str  # "YYYY-MM-DD"
    end: str  # "YYYY-MM-DD"
    warnings: tuple[ValidationWarning, ...]

    def to_dict(self) -> dict[str, Any]:
        """JSON-native form: equal to its own json.loads(json.dumps(...)) round trip."""
        return {
            "n_rows": self.n_rows,
            "tickers": list(self.tickers),
            "start": self.start,
            "end": self.end,
            "warnings": [
                {"code": w.code, "date": w.date, "ticker": w.ticker, "value": w.value}
                for w in self.warnings
            ],
        }


def _day(ts: pd.Timestamp) -> str:
    return ts.strftime("%Y-%m-%d")


def validate_prices(close: pd.DataFrame, *, max_abs_return: float = 0.5) -> ValidationReport:
    """Pure check of a close-price frame. Raises DataValidationError; never touches disk.

    Errors: empty frame, non-datetime or tz-aware index, duplicate or unsorted dates,
    NaN/inf, price <= 0. A daily return with abs(r) > max_abs_return is a warning, not an error.
    Raises ConfigError unless max_abs_return is a finite real number > 0 (bool rejected).
    """
    if (
        isinstance(max_abs_return, bool)
        or not isinstance(max_abs_return, numbers.Real)
        or not math.isfinite(max_abs_return)
        or max_abs_return <= 0
    ):
        raise ConfigError(f"max_abs_return must be a finite number > 0, got {max_abs_return!r}")

    if close.empty:
        raise DataValidationError("price frame is empty")

    index = close.index
    if not isinstance(index, pd.DatetimeIndex):
        raise DataValidationError(f"index must be a DatetimeIndex, got {type(index).__name__}")
    if index.tz is not None:
        raise DataValidationError(f"index must be timezone-naive, got tz={index.tz}")

    duplicated = index[index.duplicated()]
    if len(duplicated) > 0:
        raise DataValidationError(f"duplicate date {_day(duplicated[0])}")

    if not index.is_monotonic_increasing:
        pos = int(np.flatnonzero(index[1:] < index[:-1])[0]) + 1
        raise DataValidationError(
            f"dates not increasing: {_day(index[pos])} comes after {_day(index[pos - 1])}"
        )

    tickers = [str(c) for c in close.columns]
    values = close.to_numpy(dtype=np.float64)

    bad = ~np.isfinite(values)
    if bad.any():
        row, col = np.argwhere(bad)[0]
        raise DataValidationError(
            f"non-finite price {values[row, col]} at {_day(index[row])} for {tickers[col]}"
        )

    bad = values <= 0
    if bad.any():
        row, col = np.argwhere(bad)[0]
        raise DataValidationError(
            f"price <= 0 ({values[row, col]}) at {_day(index[row])} for {tickers[col]}"
        )

    returns = values[1:] / values[:-1] - 1.0
    warnings = sorted(
        (
            ValidationWarning(
                code=EXTREME_RETURN,
                date=_day(index[row + 1]),
                ticker=tickers[col],
                value=float(returns[row, col]),
            )
            for row, col in np.argwhere(np.abs(returns) > max_abs_return)
        ),
        key=lambda w: (w.date, w.ticker),
    )

    return ValidationReport(
        n_rows=len(close),
        tickers=tuple(sorted(tickers)),
        start=_day(index[0]),
        end=_day(index[-1]),
        warnings=tuple(warnings),
    )
