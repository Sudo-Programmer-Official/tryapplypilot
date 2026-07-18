from __future__ import annotations

from datetime import datetime, timezone
import json
import logging


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        for attribute in ("operation_name", "attempt", "delay_seconds", "connector_key"):
            if hasattr(record, attribute):
                payload[attribute] = getattr(record, attribute)
        return json.dumps(payload)


def configure_logging(level: str) -> None:
    root_logger = logging.getLogger()
    if any(isinstance(handler.formatter, JsonLogFormatter) for handler in root_logger.handlers):
        root_logger.setLevel(level)
        return

    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

