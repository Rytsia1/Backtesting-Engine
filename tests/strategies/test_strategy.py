from typing import ClassVar

import numpy as np
import pandas as pd
import pytest
from hypothesis import given
from hypothesis import strategies as st

from qrbt.engine.data import MarketData
from qrbt.engine.errors import WeightConstraintError
from qrbt.engine.strategies import BaseStrategy, Strategy, Weights

TICKERS = ["AAA", "BBB"]


def make_md(aaa: list[float], bbb: list[float]) -> MarketData:
    index = pd.DatetimeIndex(
        pd.date_range("2024-01-01", periods=len(aaa), freq="D"), name="date"
    ).as_unit("ns")
    close = pd.DataFrame({"AAA": aaa, "BBB": bbb}, index=index, dtype="float64")
    return MarketData(close=close, dataset_hash="0" * 64, calendar="XNYS")


def default_md() -> MarketData:
    return make_md(
        [100.0, 101.0, 99.0, 104.0, 104.0, 98.0, 110.0],
        [50.0, 52.0, 49.0, 51.0, 52.0, 49.0, 55.0],
    )


class PickWinner(BaseStrategy):
    """Target the ticker with the higher return over the history; None on a tie."""

    name: ClassVar[str] = "pick_winner"
    version: ClassVar[str] = "test"

    def __init__(self, lookback: int) -> None:
        self.lookback = lookback

    def signal(self, history: MarketData) -> Weights | None:
        close = history.close
        aaa = float(close["AAA"].iloc[-1] / close["AAA"].iloc[0])
        bbb = float(close["BBB"].iloc[-1] / close["BBB"].iloc[0])
        if aaa == bbb:
            return None
        return {"AAA": 1.0} if aaa > bbb else {"BBB": 0.5}


class Spy(BaseStrategy):
    """Test double: records the history length of every call and holds 100% cash."""

    name: ClassVar[str] = "spy"
    version: ClassVar[str] = "test"

    def __init__(self, lookback: int) -> None:
        self.lookback = lookback
        self.calls: list[int] = []

    def signal(self, history: MarketData) -> Weights | None:
        self.calls.append(len(history.close))
        return {}


class Fixed(BaseStrategy):
    name: ClassVar[str] = "fixed"
    version: ClassVar[str] = "test"

    def __init__(self, target: Weights | None) -> None:
        self.lookback = 1
        self.target = target

    def signal(self, history: MarketData) -> Weights | None:
        return self.target


def expected_rows(strategy: BaseStrategy, md: MarketData) -> pd.DataFrame:
    """Reference: call signal on every causal slice, one bar at a time."""
    rows = []
    for t in range(len(md.close)):
        weights = None if t + 1 < strategy.lookback else strategy.signal(md._slice_by_index(t))
        rows.append(
            [np.nan] * len(TICKERS)
            if weights is None
            else [float(weights.get(k, 0.0)) for k in TICKERS]
        )
    return pd.DataFrame(rows, index=md.close.index, columns=TICKERS, dtype="float64")


# --- shape and causal equivalence ---


def test_strategies_satisfy_the_protocol() -> None:
    strategy: Strategy = PickWinner(lookback=3)
    assert strategy.lookback == 3


@pytest.mark.parametrize("lookback", [1, 2, 3, 7])
def test_signal_all_matches_iterative_signal(lookback: int) -> None:
    md = default_md()
    strategy = PickWinner(lookback)
    pd.testing.assert_frame_equal(strategy.signal_all(md), expected_rows(strategy, md))


def test_signal_all_shape() -> None:
    md = default_md()
    out = PickWinner(lookback=2).signal_all(md)
    assert out.index.equals(md.close.index)
    assert out.columns.tolist() == TICKERS
    assert all(dtype == np.float64 for dtype in out.dtypes)


# --- warm-up ---


@pytest.mark.parametrize("lookback", [1, 3, 7])
def test_warm_up_skips_signal_and_yields_nan(lookback: int) -> None:
    md = default_md()
    spy = Spy(lookback)
    out = spy.signal_all(md)
    assert spy.calls == list(range(lookback, len(md.close) + 1))
    assert out.iloc[: lookback - 1].isna().all().all()
    assert (out.iloc[lookback - 1 :] == 0.0).all().all()


def test_lookback_longer_than_data_never_calls_signal() -> None:
    spy = Spy(lookback=8)
    out = spy.signal_all(default_md())
    assert spy.calls == []
    assert out.isna().all().all()


# --- None, empty, partial, invalid ---


def test_none_gives_a_nan_row() -> None:
    assert Fixed(None).signal_all(default_md()).isna().all().all()


def test_empty_weights_give_an_all_cash_zero_row() -> None:
    assert (Fixed({}).signal_all(default_md()) == 0.0).all().all()


def test_missing_tickers_are_explicit_zero_targets() -> None:
    out = Fixed({"BBB": 0.5}).signal_all(default_md())
    assert (out["AAA"] == 0.0).all()
    assert (out["BBB"] == 0.5).all()


@pytest.mark.parametrize(
    "target", [{"AAA": 1.5}, {"AAA": -0.1}, {"ZZZ": 0.1}, {"AAA": float("nan")}]
)
def test_invalid_weights_from_signal_raise(target: Weights) -> None:
    with pytest.raises(WeightConstraintError):
        Fixed(target).signal_all(default_md())


# --- anti look-ahead ---

PRICE = st.floats(min_value=1.0, max_value=1000.0, allow_nan=False, allow_infinity=False)


@given(st.data())
def test_future_prices_never_change_past_targets(data: st.DataObject) -> None:
    n = data.draw(st.integers(min_value=4, max_value=12))
    aaa = data.draw(st.lists(PRICE, min_size=n, max_size=n))
    bbb = data.draw(st.lists(PRICE, min_size=n, max_size=n))
    t = data.draw(st.integers(min_value=0, max_value=n - 2))
    future = n - t - 1
    aaa2 = aaa[: t + 1] + data.draw(st.lists(PRICE, min_size=future, max_size=future))
    bbb2 = bbb[: t + 1] + data.draw(st.lists(PRICE, min_size=future, max_size=future))
    strategy = PickWinner(lookback=data.draw(st.integers(min_value=1, max_value=4)))
    before = strategy.signal_all(make_md(aaa, bbb)).iloc[: t + 1]
    after = strategy.signal_all(make_md(aaa2, bbb2)).iloc[: t + 1]
    pd.testing.assert_frame_equal(before, after)
