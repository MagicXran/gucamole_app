"""
Backend 公共运行时工具。
"""

import json
import logging
import os
from datetime import datetime, timezone


def get_instance_id() -> str:
    return (
        os.environ.get("PORTAL_INSTANCE_ID")
        or os.environ.get("COMPOSE_PROJECT_NAME")
        or "local"
    )


def get_service_name(default: str = "portal-backend") -> str:
    return os.environ.get("PORTAL_SERVICE_NAME") or default


class StructuredLogFormatter(logging.Formatter):
    """把普通 logging 记录统一格式化为 JSON 行日志。"""

    def __init__(self, instance_id: str | None = None, service_name: str | None = None):
        super().__init__()
        self._instance_id = instance_id or get_instance_id()
        self._service_name = service_name or get_service_name()

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "instance_id": getattr(record, "instance_id", self._instance_id),
            "service_name": getattr(record, "service_name", self._service_name),
            "event": getattr(record, "event", "log"),
            "message": record.getMessage(),
        }

        fields = getattr(record, "fields", None) or {}
        if isinstance(fields, dict):
            payload.update(fields)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


def log_extra(event: str, **fields) -> dict:
    return {"event": event, "fields": fields}


def configure_logging(
    level: int | str = logging.INFO,
    *,
    replace_handlers: bool = False,
) -> bool:
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)

    root = logging.getLogger()
    if root.handlers and not replace_handlers:
        return False

    handler = logging.StreamHandler()
    handler.setFormatter(StructuredLogFormatter())
    if replace_handlers:
        root.handlers.clear()
    root.setLevel(level)
    root.addHandler(handler)
    return True
