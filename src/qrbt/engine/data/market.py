import pandas as pd


class MarketData:
    """Frozen. Validated adjusted close prices plus their dataset identity."""

    close: pd.DataFrame
    dataset_hash: str
    calendar: str
    open: pd.DataFrame | None

    def __init__(
        self,
        close: pd.DataFrame,
        dataset_hash: str,
        calendar: str,
        open: pd.DataFrame | None = None,
    ) -> None:
        raise NotImplementedError
