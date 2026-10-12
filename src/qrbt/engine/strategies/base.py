from abc import ABC, abstractmethod
from typing import ClassVar, Protocol

import numpy as np
import pandas as pd

from qrbt.engine.data.market import MarketData
from qrbt.engine.strategies.weights import Weights, validate_weights


class Strategy(Protocol):
    """Produces target weights only: never sees cash, holdings, prices of execution or costs.

    lookback is the minimum number of bars in `history` before signal is called; the engine
    adds no implicit offset (a 20-day momentum needs lookback = 21).
    """

    name: ClassVar[str]
    version: ClassVar[str]
    lookback: int

    def signal(self, history: MarketData) -> Weights | None:
        """Target weights after the close of the last bar in history; None = no change."""
        ...

    def signal_all(self, data: MarketData) -> pd.DataFrame:
        """Targets for every decision date: index = dates, columns = sorted tickers,
        NaN row = no change."""
        ...


class BaseStrategy(ABC):
    name: ClassVar[str]
    version: ClassVar[str]
    lookback: int

    @abstractmethod
    def signal(self, history: MarketData) -> Weights | None: ...

    def signal_all(self, data: MarketData) -> pd.DataFrame:
        """Default: call signal on every causal prefix, so it cannot see the future.

        Bars with fewer than `lookback` rows are warm-up (NaN, signal not called). A returned
        mapping is validated; tickers it omits are explicit zero targets.
        """
        close = data.close
        tickers = [str(c) for c in close.columns]
        rows = np.full((len(close), len(tickers)), np.nan)
        for t in range(self.lookback - 1, len(close)):
            weights = self.signal(data._slice_by_index(t))
            if weights is None:
                continue
            validate_weights(weights, tickers)
            rows[t] = [float(weights.get(ticker, 0.0)) for ticker in tickers]
        return pd.DataFrame(rows, index=close.index, columns=close.columns)
