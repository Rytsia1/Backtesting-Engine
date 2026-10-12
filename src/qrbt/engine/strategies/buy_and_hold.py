from typing import ClassVar

from qrbt.engine.data.market import MarketData
from qrbt.engine.strategies.base import BaseStrategy
from qrbt.engine.strategies.weights import Weights


class BuyAndHold(BaseStrategy):
    """Buy once on the first eligible bar, then let the weights drift (never rebalance).

    weights=None means equal weight 1/N over the tickers in the data. Stateless: whether a bar
    is the first one is read from len(history), not remembered.
    """

    name: ClassVar[str] = "buy_and_hold"
    version: ClassVar[str] = "1"

    def __init__(self, weights: Weights | None = None) -> None:
        self.lookback = 1
        self._weights = None if weights is None else dict(weights)

    def signal(self, history: MarketData) -> Weights | None:
        tickers = history.close.columns
        if len(history.close) != self.lookback:
            return None
        if self._weights is None:
            return {str(t): 1.0 / len(tickers) for t in tickers}
        return dict(self._weights)
