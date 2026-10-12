import qrbt.engine.data
import qrbt.engine.metrics
import qrbt.engine.sim
import qrbt.engine.strategies
import qrbt.engine.validation


def test_package_imports() -> None:
    assert qrbt.engine.__name__ == "qrbt.engine"
