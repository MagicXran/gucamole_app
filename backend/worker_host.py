"""
Reusable long-running host loop for WorkerAgent.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from threading import Event
from typing import Any, Callable


logger = logging.getLogger(__name__)


@dataclass
class WorkerHost:
    agent: Any
    interval_seconds: float = 5.0
    sleep_fn: Callable[[float], None] = time.sleep

    def run(self, *, stop_event: Event | None = None) -> None:
        stop_event = stop_event or Event()
        while not stop_event.is_set():
            try:
                self.agent.run_once()
            except Exception as exc:  # pragma: no cover - exercised by tests
                logger.exception("worker host loop iteration failed: %s", exc)
            self.sleep_fn(self.interval_seconds)
