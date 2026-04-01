"""Minimal JSON-line structured logging helpers."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from decimal import Decimal


def _json_default(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


def log_event(logger: logging.Logger, level: int, event: str, **fields):
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": logging.getLevelName(level),
        "event": event,
        "logger": logger.name,
    }
    for key, value in fields.items():
        if value is not None:
            payload[key] = value
    logger.log(level, json.dumps(payload, ensure_ascii=False, default=_json_default))


class StructuredLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        try:
            json.loads(message)
            return message
        except Exception:
            return super().format(record)
