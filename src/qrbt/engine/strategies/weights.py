import math
import numbers
from collections.abc import Mapping, Sequence

from qrbt.engine.errors import WeightConstraintError

Weights = Mapping[str, float]
"""Target weights after a decision close: ticker -> weight. Cash is 1 - sum(weights)."""

WEIGHT_TOLERANCE = 1e-12


def validate_weights(weights: Weights, tickers: Sequence[str]) -> None:
    """Long-only, no leverage: every weight is a finite real >= 0 (bool rejected), every ticker
    is in `tickers`, and the total is at most 1 + 1e-12. Never clips; raises
    WeightConstraintError on the first violation, checking tickers in sorted order."""
    known = set(tickers)
    for ticker in sorted(weights):
        w = weights[ticker]
        if ticker not in known:
            raise WeightConstraintError(f"weight for unknown ticker {ticker!r}")
        if isinstance(w, bool) or not isinstance(w, numbers.Real):
            raise WeightConstraintError(f"weight for {ticker} must be a real number, got {w!r}")
        if not math.isfinite(w):
            raise WeightConstraintError(f"weight for {ticker} must be finite, got {w!r}")
        if w < 0:
            raise WeightConstraintError(f"weight for {ticker} must be >= 0 (long-only), got {w!r}")
    # fsum is exactly rounded, so the total does not depend on iteration order.
    total = math.fsum(weights.values())
    if total > 1.0 + WEIGHT_TOLERANCE:
        raise WeightConstraintError(f"total weight {total!r} exceeds 1 + {WEIGHT_TOLERANCE}")
