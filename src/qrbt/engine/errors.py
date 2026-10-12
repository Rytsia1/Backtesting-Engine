class EngineError(Exception):
    """Base for every error raised by the engine."""


class ConfigError(EngineError):
    """Invalid configuration: start after end, negative cost, unknown or unsupported mode."""


class DataValidationError(EngineError):
    """Snapshot has NaN, duplicate or unsorted dates, price <= 0, or a hash mismatch."""


class InsufficientDataError(EngineError):
    """Not enough data for the lookback plus at least 2 evaluation periods."""


class WeightConstraintError(EngineError):
    """Negative or NaN weight, total weight > 1 + 1e-12, or unknown ticker."""


class StrategyContractError(EngineError):
    """signal_all output is malformed or not equal to the default implementation."""
