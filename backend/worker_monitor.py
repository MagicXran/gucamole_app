"""
Background maintenance for worker liveness and recovery.
"""

from __future__ import annotations

import logging

from backend.database import CONFIG, db
from backend.worker_repository import MySQLWorkerRepository
from backend.worker_service import WorkerService


logger = logging.getLogger(__name__)

WORKER_HEARTBEAT_TIMEOUT_SECONDS = 45
WORKER_ASSIGNED_STALL_TIMEOUT_SECONDS = int(CONFIG.get("monitor", {}).get("worker_assigned_stall_timeout_seconds", 90))
worker_service = WorkerService(repo=MySQLWorkerRepository(db))


def reconcile_offline_workers():
    result = worker_service.reconcile_offline_workers(timeout_seconds=WORKER_HEARTBEAT_TIMEOUT_SECONDS)
    if result["offline_worker_count"] > 0:
        logger.warning(
            "检测到离线 Worker: %d, 回队: %d, 失败: %d",
            result["offline_worker_count"],
            len(result["requeued_task_ids"]),
            len(result["failed_task_ids"]),
        )
    return result


def reconcile_stalled_assigned_tasks():
    result = worker_service.recover_stalled_assigned_tasks(timeout_seconds=WORKER_ASSIGNED_STALL_TIMEOUT_SECONDS)
    if result["failed_task_ids"]:
        logger.warning(
            "检测到卡死 assigned 任务: %d, 已失败: %d, 跳过: %d",
            result["stale_task_count"],
            len(result["failed_task_ids"]),
            len(result["skipped_task_ids"]),
        )
    return result
