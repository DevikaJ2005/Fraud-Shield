import logging

from pythonjsonlogger import jsonlogger


def configure_logging() -> None:
    root = logging.getLogger()
    if root.handlers:
        for handler in root.handlers:
            handler.setFormatter(_formatter())
        root.setLevel(logging.INFO)
        return

    handler = logging.StreamHandler()
    handler.setFormatter(_formatter())
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def _formatter() -> jsonlogger.JsonFormatter:
    return jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s %(transaction_id)s %(model_version)s %(fraud_probability)s %(severity)s %(ring_detected)s"
    )
