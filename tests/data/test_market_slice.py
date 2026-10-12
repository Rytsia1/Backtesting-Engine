from dataclasses import FrozenInstanceError
from typing import NoReturn

import numpy as np
import pandas as pd
import pytest

import qrbt.engine.data.market as market_module
from qrbt.engine.data import MarketData

DATES = ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-08"]
HASH = "0" * 64
CALENDAR = "XNYS"


def make_md(*, with_open: bool = False) -> MarketData:
    close = pd.DataFrame(
        {
            "AAA": [100.0, 101.0, 102.0, 101.5, 103.0],
            "BBB": [50.0, 50.5, 49.8, 50.2, 51.0],
        },
        index=pd.DatetimeIndex(DATES, name="date").as_unit("ns"),
    )
    return MarketData(
        close=close, dataset_hash=HASH, calendar=CALENDAR, open=close * 0.99 if with_open else None
    )


@pytest.mark.parametrize("end_idx", [0, 2, 4])
def test_slice_is_an_inclusive_prefix(end_idx: int) -> None:
    md = make_md()
    sliced = md._slice_by_index(end_idx)
    assert len(sliced.close) == end_idx + 1
    pd.testing.assert_frame_equal(sliced.close, md.close.iloc[: end_idx + 1])


def test_slice_keeps_canonical_form_identity_and_open() -> None:
    md = make_md(with_open=True)
    sliced = md._slice_by_index(2)
    assert isinstance(sliced, MarketData)
    assert sliced.close.index.dtype == np.dtype("datetime64[ns]")
    assert sliced.close.index.name == "date"
    assert sliced.close.columns.tolist() == ["AAA", "BBB"]
    assert all(dtype == np.float64 for dtype in sliced.close.dtypes)
    assert sliced.dataset_hash == HASH
    assert sliced.calendar == CALENDAR
    parent_open, sliced_open = md.open, sliced.open
    assert parent_open is not None and sliced_open is not None
    pd.testing.assert_frame_equal(sliced_open, parent_open.iloc[:3])


def test_slice_does_not_revalidate(monkeypatch: pytest.MonkeyPatch) -> None:
    md = make_md(with_open=True)

    def forbidden(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("slicing re-ran price validation")

    monkeypatch.setattr(market_module, "_check_prices", forbidden)
    monkeypatch.setattr(market_module, "validate_prices", forbidden)
    assert len(md._slice_by_index(3).close) == 4


def test_slice_is_isolated_from_parent_and_callers() -> None:
    md = make_md()
    sliced = md._slice_by_index(2)
    leaked_slice = sliced.close
    leaked_slice.iloc[0, 0] = 999.0
    leaked_parent = md.close
    leaked_parent.iloc[0, 0] = 555.0
    assert sliced.close.iloc[0, 0] == 100.0
    assert md.close.iloc[0, 0] == 100.0


def test_slice_is_frozen() -> None:
    sliced = make_md()._slice_by_index(1)
    with pytest.raises(FrozenInstanceError):
        setattr(sliced, "calendar", "XIDX")  # noqa: B010


@pytest.mark.parametrize("end_idx", [-1, 5, 10])
def test_out_of_range_end_idx_raises(end_idx: int) -> None:
    with pytest.raises(IndexError):
        make_md()._slice_by_index(end_idx)
