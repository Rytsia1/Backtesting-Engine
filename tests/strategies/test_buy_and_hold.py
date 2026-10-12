import math

import pandas as pd
import pytest

from qrbt.engine.data import MarketData
from qrbt.engine.errors import WeightConstraintError
from qrbt.engine.strategies import BuyAndHold, Strategy, Weights


def make_md(columns: dict[str, list[float]]) -> MarketData:
    n = len(next(iter(columns.values())))
    index = pd.DatetimeIndex(pd.date_range("2024-01-01", periods=n, freq="D"), name="date").as_unit(
        "ns"
    )
    close = pd.DataFrame(columns, index=index, dtype="float64")
    return MarketData(close=close, dataset_hash="0" * 64, calendar="XNYS")


def two_tickers() -> MarketData:
    return make_md({"AAA": [100.0, 101.0, 99.0, 104.0], "BBB": [50.0, 52.0, 49.0, 51.0]})


def test_metadata_and_protocol() -> None:
    strategy: Strategy = BuyAndHold()
    assert strategy.lookback == 1
    assert BuyAndHold.name == "buy_and_hold"
    assert BuyAndHold.version


def test_default_is_equal_weight_on_first_bar_then_none() -> None:
    out = BuyAndHold().signal_all(two_tickers())
    assert out.iloc[0].tolist() == [0.5, 0.5]
    assert out.iloc[1:].isna().all().all()


def test_equal_weight_with_three_tickers() -> None:
    md = make_md({"AAA": [1.0, 2.0], "BBB": [3.0, 4.0], "CCC": [5.0, 6.0]})
    first = BuyAndHold().signal_all(md).iloc[0].tolist()
    assert first == [1 / 3, 1 / 3, 1 / 3]
    assert math.fsum(first) <= 1.0 + 1e-12


def test_custom_weights_on_first_bar_then_none() -> None:
    out = BuyAndHold({"AAA": 0.6}).signal_all(two_tickers())
    assert out.iloc[0].tolist() == [0.6, 0.0]
    assert out.iloc[1:].isna().all().all()


def test_signal_targets_only_the_first_eligible_bar() -> None:
    md = two_tickers()
    strategy = BuyAndHold()
    assert strategy.signal(md._slice_by_index(0)) == {"AAA": 0.5, "BBB": 0.5}
    for t in range(1, len(md.close)):
        assert strategy.signal(md._slice_by_index(t)) is None


@pytest.mark.parametrize("weights", [{"ZZZ": 1.0}, {"AAA": 0.8, "BBB": 0.8}, {"AAA": -0.1}])
def test_invalid_custom_weights_raise(weights: Weights) -> None:
    with pytest.raises(WeightConstraintError):
        BuyAndHold(weights).signal_all(two_tickers())


def test_caller_mutation_after_construction_does_not_leak() -> None:
    weights = {"AAA": 0.6}
    strategy = BuyAndHold(weights)
    weights["AAA"] = 0.9
    assert strategy.signal(two_tickers()._slice_by_index(0)) == {"AAA": 0.6}


def test_returned_weights_cannot_change_the_strategy() -> None:
    strategy = BuyAndHold({"AAA": 0.6})
    first = strategy.signal(two_tickers()._slice_by_index(0))
    assert isinstance(first, dict)
    first["AAA"] = 0.1
    assert strategy.signal(two_tickers()._slice_by_index(0)) == {"AAA": 0.6}


def test_signal_all_is_deterministic() -> None:
    md = two_tickers()
    strategy = BuyAndHold()
    pd.testing.assert_frame_equal(strategy.signal_all(md), strategy.signal_all(md))
