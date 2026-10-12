from typing import Any

import pandas as pd


class ValidationWarning:
    """Frozen. A non-fatal finding, e.g. an extreme daily return."""

    code: str
    date: str  # "YYYY-MM-DD"
    ticker: str
    value: float

    def __init__(self, code: str, date: str, ticker: str, value: float) -> None:
        raise NotImplementedError


class ValidationReport:
    """Frozen. Summary of a price frame that passed validation."""

    n_rows: int
    tickers: tuple[str, ...]
    start: str  # "YYYY-MM-DD"
    end: str  # "YYYY-MM-DD"
    warnings: tuple[ValidationWarning, ...]

    def __init__(
        self,
        n_rows: int,
        tickers: tuple[str, ...],
        start: str,
        end: str,
        warnings: tuple[ValidationWarning, ...],
    ) -> None:
        raise NotImplementedError

    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError


def validate_prices(close: pd.DataFrame, *, max_abs_return: float = 0.5) -> ValidationReport:
    """Pure check of a close-price frame. Raises DataValidationError; never touches disk."""
    raise NotImplementedError
