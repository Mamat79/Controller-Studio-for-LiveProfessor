import logging

from silemio_control_hub.runtime.logging import configure_runtime_logging


def test_runtime_logging_writes_to_a_rotating_product_log(tmp_path):
    path = tmp_path / "product.log"
    assert configure_runtime_logging("INFO", path) == path

    logger = logging.getLogger("silemio_control_hub.test")
    logger.info("runtime log proof")
    for handler in logging.getLogger("silemio_control_hub").handlers:
        handler.flush()

    assert "runtime log proof" in path.read_text(encoding="utf-8")
