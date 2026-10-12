import math
from typing import Any, cast

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from qrbt.engine.errors import WeightConstraintError
from qrbt.engine.strategies import Weights, validate_weights

TICKERS = ["AAA", "BBB", "CCC"]


# --- valid ---


@pytest.mark.parametrize(
    "weights",
    [
        {"AAA": 1.0},
        {"AAA": 0.25, "BBB": 0.25, "CCC": 0.5},
        {"AAA": 0.3, "BBB": 0.2},  # 50% cash
        {},  # 100% cash
        {"AAA": 0.0},
        {"AAA": 1},  # int is numeric
        {"AAA": np.float64(0.5), "BBB": np.int64(0)},
        {"AAA": 1.0 + 1e-13},  # within the 1 + 1e-12 tolerance
        {"AAA": 0.5, "BBB": 0.5 + 1e-13},
    ],
    ids=[
        "full",
        "full-three",
        "partial",
        "empty",
        "zero",
        "int",
        "numpy-scalars",
        "tolerance-one",
        "tolerance-two",
    ],
)
def test_valid_weights_pass(weights: Weights) -> None:
    validate_weights(weights, TICKERS)


def test_validation_does_not_modify_weights() -> None:
    weights = {"BBB": 0.4, "AAA": 0.6}
    validate_weights(weights, TICKERS)
    assert weights == {"BBB": 0.4, "AAA": 0.6}
    assert list(weights) == ["BBB", "AAA"]


# --- invalid ---


@pytest.mark.parametrize("bad", [-0.1, -1e-300, -1])
def test_negative_weight_raises(bad: float) -> None:
    with pytest.raises(WeightConstraintError, match="AAA"):
        validate_weights({"AAA": bad, "BBB": 0.5}, TICKERS)


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf], ids=["nan", "inf", "-inf"])
def test_non_finite_weight_raises(bad: float) -> None:
    with pytest.raises(WeightConstraintError, match="AAA"):
        validate_weights({"AAA": bad}, TICKERS)


@pytest.mark.parametrize("bad", [True, False, np.bool_(True)], ids=["True", "False", "np.bool_"])
def test_boolean_weight_raises(bad: object) -> None:
    with pytest.raises(WeightConstraintError, match="AAA"):
        validate_weights(cast(Any, {"AAA": bad}), TICKERS)


@pytest.mark.parametrize("bad", ["0.5", None, [0.5]], ids=["str", "None", "list"])
def test_non_numeric_weight_raises(bad: object) -> None:
    with pytest.raises(WeightConstraintError, match="AAA"):
        validate_weights(cast(Any, {"AAA": bad}), TICKERS)


@pytest.mark.parametrize(
    "weights",
    [{"AAA": 1.0 + 1e-11}, {"AAA": 0.6, "BBB": 0.5}, {"AAA": 0.5, "BBB": 0.5, "CCC": 1e-11}],
    ids=["single", "two", "three"],
)
def test_total_above_tolerance_raises(weights: Weights) -> None:
    with pytest.raises(WeightConstraintError):
        validate_weights(weights, TICKERS)


def test_unknown_ticker_raises() -> None:
    with pytest.raises(WeightConstraintError, match="ZZZ"):
        validate_weights({"AAA": 0.5, "ZZZ": 0.1}, TICKERS)


def test_unknown_ticker_raises_even_with_zero_weight() -> None:
    with pytest.raises(WeightConstraintError, match="ZZZ"):
        validate_weights({"ZZZ": 0.0}, TICKERS)


# --- properties ---


@given(st.lists(st.floats(min_value=0.0, max_value=1.0), min_size=1, max_size=3))
def test_any_nonnegative_allocation_summing_to_at_most_one_passes(raw: list[float]) -> None:
    total = math.fsum(raw)
    scale = 1.0 / total if total > 1.0 else 1.0
    weights = {t: w * scale for t, w in zip(TICKERS, raw, strict=False)}
    validate_weights(weights, TICKERS)


@given(
    st.lists(st.floats(min_value=0.0, max_value=1.0), min_size=1, max_size=3),
    st.floats(min_value=1e-9, max_value=1.0),
)
def test_scaling_a_full_allocation_above_one_raises(raw: list[float], excess: float) -> None:
    total = math.fsum(raw)
    if total == 0.0:
        raw, total = [1.0], 1.0
    weights = {t: w / total * (1.0 + excess) for t, w in zip(TICKERS, raw, strict=False)}
    with pytest.raises(WeightConstraintError):
        validate_weights(weights, TICKERS)
