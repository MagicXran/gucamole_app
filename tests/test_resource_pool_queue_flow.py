from __future__ import annotations

from datetime import datetime, timedelta

from backend.resource_pool_service import ResourcePoolService

LIVE_QUEUE_STATUSES = {"queued", "ready", "launching"}
OCCUPIED_SESSION_STATUSES = {"active", "reclaim_pending"}


class FakeQueueFlowDB:
    def __init__(
        self,
        *,
        launch_targets=None,
        pools=None,
        members=None,
        queue_entries=None,
        active_sessions=None,
    ):
        self.launch_targets = dict(launch_targets or {})
        self.pools = {
            int(pool["id"]): dict(pool)
            for pool in (pools or [])
        }
        self.members = {
            int(member["id"]): dict(member)
            for member in (members or [])
        }
        self.queue_entries = [dict(entry) for entry in (queue_entries or [])]
        self.active_sessions = [dict(session) for session in (active_sessions or [])]
        self._next_queue_id = (
            max((int(entry["id"]) for entry in self.queue_entries), default=0) + 1
        )

    def execute_query(self, query: str, params=None, fetch_one: bool = False):
        params = params or {}

        if "/* rps:get_lock */" in query:
            row = {"locked": 1}
            return row if fetch_one else [row]
        if "/* rps:release_lock */" in query:
            row = {"released": 1}
            return row if fetch_one else [row]

        if "/* rps:get_live_queue_state */" in query:
            rows = [
                {"id": entry["id"], "status": entry["status"]}
                for entry in self._live_queue_entries()
                if int(entry["user_id"]) == int(params["user_id"])
                and int(entry["pool_id"]) == int(params["pool_id"])
            ]
            rows.sort(key=lambda row: int(row["id"]))
            row = rows[0] if rows else None
            return row if fetch_one else rows

        if "/* rps:get_live_active_session */" in query:
            rows = [
                {
                    "session_id": session["session_id"],
                    "status": session["status"],
                }
                for session in self.active_sessions
                if int(session["user_id"]) == int(params["user_id"])
                and int(session["pool_id"]) == int(params["pool_id"])
                and session["status"] in OCCUPIED_SESSION_STATUSES
            ]
            row = rows[0] if rows else None
            return row if fetch_one else rows

        if "/* rps:list_pool_members_with_load */" in query:
            exclude_queue_id = params.get("exclude_queue_id")
            rows = []
            for member in self.members.values():
                if int(member["pool_id"]) != int(params["pool_id"]):
                    continue
                if not member.get("is_active", True):
                    continue
                if int(params["user_id"]) not in set(member.get("allowed_users", [])):
                    continue
                active_count = self._member_active_count(
                    member_id=int(member["id"]),
                    exclude_queue_id=exclude_queue_id,
                )
                if active_count >= int(member.get("member_max_concurrent", 1)):
                    continue
                rows.append(
                    {
                        "id": int(member["id"]),
                        "pool_id": int(member["pool_id"]),
                        "member_max_concurrent": int(member.get("member_max_concurrent", 1)),
                        "active_count": active_count,
                    }
                )
            rows.sort(key=lambda row: (int(row["active_count"]), int(row["id"])))
            return rows[0] if fetch_one else rows

        if "/* rps:has_accessible_member */" in query:
            row = None
            for member in self.members.values():
                if (
                    int(member["pool_id"]) == int(params["pool_id"])
                    and member.get("is_active", True)
                    and int(params["user_id"]) in set(member.get("allowed_users", []))
                ):
                    row = {"ok": 1}
                    break
            return row if fetch_one else ([row] if row else [])

        if "/* rps:get_pool_live_queue_count */" in query:
            count = len(
                [
                    entry
                    for entry in self._live_queue_entries()
                    if int(entry["pool_id"]) == int(params["pool_id"])
                ]
            )
            row = {"live_queue_count": count}
            return row if fetch_one else [row]

        if "/* rps:get_pool_by_id */" in query:
            pool = self.pools.get(int(params["pool_id"]))
            if pool and bool(pool.get("is_active", True)):
                row = {"id": int(pool["id"]), "max_concurrent": int(pool["max_concurrent"])}
            else:
                row = None
            return row if fetch_one else ([row] if row else [])

        if "/* rps:get_pool_active_count */" in query:
            count = len(
                [
                    session
                    for session in self.active_sessions
                    if int(session["pool_id"]) == int(params["pool_id"])
                    and session["status"] in OCCUPIED_SESSION_STATUSES
                ]
            )
            row = {"active_count": count}
            return row if fetch_one else [row]

        if "/* rps:get_pool_reserved_count */" in query:
            exclude_queue_id = params.get("exclude_queue_id")
            count = len(
                [
                    entry
                    for entry in self.queue_entries
                    if int(entry["pool_id"]) == int(params["pool_id"])
                    and entry["status"] in {"ready", "launching"}
                    and (
                        exclude_queue_id is None
                        or int(entry["id"]) != int(exclude_queue_id)
                    )
                ]
            )
            row = {"ready_count": count}
            return row if fetch_one else [row]

        if "/* rps:get_latest_user_queue */" in query:
            statuses = {"queued"}
            if bool(params.get("include_launching")):
                statuses.add("launching")
            rows = [
                {"id": int(entry["id"])}
                for entry in self.queue_entries
                if int(entry["pool_id"]) == int(params["pool_id"])
                and int(entry["user_id"]) == int(params["user_id"])
                and entry["status"] in statuses
            ]
            rows.sort(key=lambda row: int(row["id"]), reverse=True)
            row = rows[0] if rows else None
            return row if fetch_one else rows

        if "/* rps:list_expired_ready_entries */" in query:
            rows = []
            for entry in self.queue_entries:
                if entry["status"] != "ready":
                    continue
                if entry.get("ready_expires_at") is None or entry["ready_expires_at"] >= params["now_ts"]:
                    continue
                if params.get("pool_id") is not None and int(entry["pool_id"]) != int(params["pool_id"]):
                    continue
                rows.append({"id": int(entry["id"])})
            rows.sort(key=lambda row: int(row["id"]))
            return rows[0] if fetch_one else rows

        if "/* rps:get_launch_target */" in query:
            row = self.launch_targets.get((int(params["user_id"]), int(params["app_id"])))
            if row is None:
                return None if fetch_one else []
            return dict(row) if fetch_one else [dict(row)]

        if "/* rps:get_queue_entry_for_consume */" in query:
            row = self._queue_row(int(params["queue_id"]), int(params["user_id"]))
            if row is None:
                return None if fetch_one else []
            payload = {
                "id": int(row["id"]),
                "pool_id": int(row["pool_id"]),
                "status": row["status"],
                "assigned_app_id": row.get("assigned_app_id"),
                "ready_expires_at": row.get("ready_expires_at"),
            }
            return payload if fetch_one else [payload]

        if "/* rps:get_member_for_user */" in query:
            member = self.members.get(int(params["member_app_id"]))
            if (
                member
                and member.get("is_active", True)
                and int(params["user_id"]) in set(member.get("allowed_users", []))
            ):
                row = {"id": int(member["id"]), "pool_id": int(member["pool_id"])}
            else:
                row = None
            return row if fetch_one else ([row] if row else [])

        if "/* rps:get_queue_status */" in query:
            row = self._queue_row(int(params["queue_id"]), int(params["user_id"]))
            if row is None:
                return None if fetch_one else []
            payload = {
                "id": int(row["id"]),
                "pool_id": int(row["pool_id"]),
                "status": row["status"],
                "ready_expires_at": row.get("ready_expires_at"),
                "cancel_reason": row.get("cancel_reason"),
            }
            return payload if fetch_one else [payload]

        if "/* rps:get_queue_position */" in query:
            count = len(
                [
                    entry
                    for entry in self._live_queue_entries()
                    if int(entry["pool_id"]) == int(params["pool_id"])
                    and int(entry["id"]) <= int(params["queue_id"])
                ]
            )
            row = {"position": count}
            return row if fetch_one else [row]

        if "/* rps:get_launching_row */" in query:
            row = next(
                (entry for entry in self.queue_entries if int(entry["id"]) == int(params["queue_id"])),
                None,
            )
            payload = None
            if row is not None:
                payload = {"id": int(row["id"]), "ready_at": row.get("ready_at")}
            return payload if fetch_one else ([payload] if payload else [])

        if "/* rps:list_dispatch_pools */" in query:
            rows = [
                {
                    "id": int(pool["id"]),
                    "dispatch_grace_seconds": int(pool.get("dispatch_grace_seconds", 120)),
                }
                for pool in self.pools.values()
                if bool(pool.get("is_active", True)) and bool(pool.get("auto_dispatch_enabled", True))
            ]
            rows.sort(key=lambda row: int(row["id"]))
            return rows[0] if fetch_one else rows

        if "/* rps:get_queue_head */" in query:
            rows = [
                {"id": int(entry["id"]), "user_id": int(entry["user_id"])}
                for entry in self.queue_entries
                if int(entry["pool_id"]) == int(params["pool_id"])
                and entry["status"] == "queued"
            ]
            rows.sort(key=lambda row: row["id"])
            row = rows[0] if rows else None
            return row if fetch_one else rows

        if "/* rps:list_live_queues */" in query:
            rows = []
            for entry in self._live_queue_entries():
                if params.get("user_id") is not None and int(entry["user_id"]) != int(params["user_id"]):
                    continue
                if params.get("requested_app_id") is not None and int(entry["requested_app_id"]) != int(params["requested_app_id"]):
                    continue
                if params.get("pool_id") is not None and int(entry["pool_id"]) != int(params["pool_id"]):
                    continue
                rows.append(
                    {
                        "id": int(entry["id"]),
                        "pool_id": int(entry["pool_id"]),
                        "user_id": int(entry["user_id"]),
                        "requested_app_id": int(entry["requested_app_id"]),
                        "assigned_app_id": entry.get("assigned_app_id"),
                        "status": entry["status"],
                    }
                )
            rows.sort(key=lambda row: int(row["id"]))
            return rows[0] if fetch_one else rows

        raise AssertionError(f"Unhandled query: {query}")

    def execute_update(self, query: str, params=None) -> int:
        params = params or {}

        if "/* rps:insert_queue_entry */" in query:
            status = (
                "launching"
                if params.get("assigned_app_id") is not None and params.get("ready_at") is not None
                else "queued"
            )
            entry = {
                "id": self._next_queue_id,
                "pool_id": int(params["pool_id"]),
                "user_id": int(params["user_id"]),
                "requested_app_id": int(params["requested_app_id"]),
                "assigned_app_id": params.get("assigned_app_id"),
                "status": status,
                "ready_at": params.get("ready_at"),
                "ready_expires_at": params.get("ready_expires_at"),
                "last_seen_at": params.get("last_seen_at"),
                "failure_count": 0,
                "last_error": None,
                "cancel_reason": None,
                "cancelled_at": None,
                "fulfilled_at": None,
            }
            self.queue_entries.append(entry)
            self._next_queue_id += 1
            return 1

        if "/* rps:expire_ready_entries */" in query:
            updated = 0
            for entry in self.queue_entries:
                if entry["status"] != "ready":
                    continue
                if entry.get("ready_expires_at") is None or entry["ready_expires_at"] >= params["now_ts"]:
                    continue
                if params.get("pool_id") is not None and int(entry["pool_id"]) != int(params["pool_id"]):
                    continue
                entry["status"] = "expired"
                entry["cancel_reason"] = "timeout"
                entry["cancelled_at"] = params["now_ts"]
                updated += 1
            return updated

        if "/* rps:queue_mark_launching */" in query:
            entry = self._queue_row(int(params["queue_id"]), int(params["user_id"]))
            if entry and entry["status"] == "ready":
                entry["status"] = "launching"
                return 1
            return 0

        if "/* rps:touch_queue */" in query:
            entry = self._queue_row(int(params["queue_id"]), int(params["user_id"]))
            if entry:
                entry["last_seen_at"] = "touched"
                return 1
            return 0

        if "/* rps:cancel_queue */" in query:
            entry = self._queue_row(int(params["queue_id"]), int(params["user_id"]))
            if entry and entry["status"] in LIVE_QUEUE_STATUSES:
                entry["status"] = "cancelled"
                entry["cancel_reason"] = "user"
                return 1
            return 0

        if "/* rps:cancel_queue_invalid */" in query:
            entry = next((item for item in self.queue_entries if int(item["id"]) == int(params["queue_id"])), None)
            if entry and entry["status"] in LIVE_QUEUE_STATUSES:
                entry["status"] = "cancelled"
                entry["cancel_reason"] = str(params["reason"])
                return 1
            return 0

        if "/* rps:cancel_queue_admin */" in query:
            entry = next((item for item in self.queue_entries if int(item["id"]) == int(params["queue_id"])), None)
            if entry and entry["status"] == "launching":
                entry["status"] = "cancelled"
                entry["cancel_reason"] = "launch_failed"
                return 1
            return 0

        if "/* rps:queue_restore_queued */" in query:
            entry = next((item for item in self.queue_entries if int(item["id"]) == int(params["queue_id"])), None)
            if entry and entry["status"] == "launching":
                entry["status"] = "queued"
                entry["failure_count"] = int(entry.get("failure_count") or 0) + 1
                entry["last_error"] = params["last_error"]
                return 1
            return 0

        if "/* rps:queue_mark_ready */" in query:
            entry = next((item for item in self.queue_entries if int(item["id"]) == int(params["queue_id"])), None)
            if entry and entry["status"] == "queued":
                entry["status"] = "ready"
                entry["ready_at"] = params["ready_at"]
                entry["ready_expires_at"] = params["ready_expires_at"]
                entry["assigned_app_id"] = params["assigned_app_id"]
                return 1
            return 0

        raise AssertionError(f"Unhandled update: {query}")

    def _queue_row(self, queue_id: int, user_id: int) -> dict | None:
        return next(
            (
                entry
                for entry in self.queue_entries
                if int(entry["id"]) == int(queue_id)
                and int(entry["user_id"]) == int(user_id)
            ),
            None,
        )

    def _live_queue_entries(self) -> list[dict]:
        return [
            entry
            for entry in self.queue_entries
            if entry["status"] in LIVE_QUEUE_STATUSES
        ]

    def _member_active_count(self, *, member_id: int, exclude_queue_id: int | None = None) -> int:
        session_count = len(
            [
                session
                for session in self.active_sessions
                if int(session["app_id"]) == member_id
                and session["status"] in OCCUPIED_SESSION_STATUSES
            ]
        )
        queue_count = len(
            [
                entry
                for entry in self.queue_entries
                if entry.get("assigned_app_id") is not None
                and int(entry["assigned_app_id"]) == member_id
                and entry["status"] in {"ready", "launching"}
                and (exclude_queue_id is None or int(entry["id"]) != int(exclude_queue_id))
            ]
        )
        return session_count + queue_count


def _build_service(**kwargs) -> tuple[ResourcePoolService, FakeQueueFlowDB, datetime]:
    now = datetime(2026, 4, 2, 9, 0, 0)
    db = FakeQueueFlowDB(**kwargs)
    service = ResourcePoolService(db=db, now_provider=lambda: now)
    return service, db, now


def test_prepare_launch_starts_when_capacity_and_member_exist():
    service, db, _ = _build_service(
        launch_targets={
            (7, 101): {"requested_app_id": 101, "pool_id": 1, "pool_name": "Pool A"},
        },
        pools=[{"id": 1, "max_concurrent": 2, "is_active": 1}],
        members=[
            {
                "id": 201,
                "pool_id": 1,
                "member_max_concurrent": 1,
                "allowed_users": {7},
                "is_active": True,
            }
        ],
    )

    result = service.prepare_launch(user_id=7, requested_app_id=101)

    assert result["status"] == "started"
    assert result["pool_id"] == 1
    assert result["member_app_id"] == 201
    assert result["queue_id"] == 1
    assert db.queue_entries[0]["status"] == "launching"
    assert db.queue_entries[0]["assigned_app_id"] == 201


def test_prepare_launch_enqueues_when_pool_already_has_live_queue_entries():
    service, db, _ = _build_service(
        launch_targets={
            (7, 101): {"requested_app_id": 101, "pool_id": 1, "pool_name": "Pool A"},
        },
        pools=[{"id": 1, "max_concurrent": 2, "is_active": 1}],
        members=[
            {
                "id": 201,
                "pool_id": 1,
                "member_max_concurrent": 1,
                "allowed_users": {7, 8},
                "is_active": True,
            }
        ],
        queue_entries=[
            {
                "id": 1,
                "pool_id": 1,
                "user_id": 8,
                "requested_app_id": 999,
                "assigned_app_id": None,
                "status": "queued",
                "ready_at": None,
                "ready_expires_at": None,
                "failure_count": 0,
                "last_error": None,
                "cancel_reason": None,
                "created_at": datetime(2026, 4, 2, 8, 59, 0),
            }
        ],
    )

    result = service.prepare_launch(user_id=7, requested_app_id=101)

    assert result["status"] == "queued"
    assert result["queue_id"] == 2
    assert result["pool_id"] == 1
    assert db.queue_entries[-1]["status"] == "queued"
    assert db.queue_entries[-1]["user_id"] == 7


def test_prepare_launch_reuses_existing_live_queue_for_same_user_and_pool():
    service, db, _ = _build_service(
        launch_targets={
            (7, 101): {"requested_app_id": 101, "pool_id": 1, "pool_name": "Pool A"},
        },
        pools=[{"id": 1, "max_concurrent": 2, "is_active": 1}],
        members=[
            {
                "id": 201,
                "pool_id": 1,
                "member_max_concurrent": 1,
                "allowed_users": {7},
                "is_active": True,
            }
        ],
        queue_entries=[
            {
                "id": 4,
                "pool_id": 1,
                "user_id": 7,
                "requested_app_id": 101,
                "assigned_app_id": None,
                "status": "queued",
                "ready_at": None,
                "ready_expires_at": None,
                "failure_count": 0,
                "last_error": None,
                "cancel_reason": None,
                "created_at": datetime(2026, 4, 2, 8, 50, 0),
            }
        ],
    )

    result = service.prepare_launch(user_id=7, requested_app_id=101)

    assert result["status"] == "queued"
    assert result["queue_id"] == 4
    assert len(db.queue_entries) == 1


def test_prepare_launch_blocks_when_same_user_already_has_active_session():
    service, db, _ = _build_service(
        launch_targets={
            (7, 101): {"requested_app_id": 101, "pool_id": 1, "pool_name": "Pool A"},
        },
        pools=[{"id": 1, "max_concurrent": 2, "is_active": 1}],
        members=[
            {
                "id": 201,
                "pool_id": 1,
                "member_max_concurrent": 1,
                "allowed_users": {7},
                "is_active": True,
            }
        ],
        active_sessions=[
            {
                "session_id": "active-user-7",
                "user_id": 7,
                "app_id": 201,
                "pool_id": 1,
                "status": "active",
            }
        ],
    )

    try:
        service.prepare_launch(user_id=7, requested_app_id=101)
        raise AssertionError("expected active session conflict")
    except ValueError as exc:
        assert "运行中的会话" in str(exc)
    assert db.queue_entries == []


def test_prepare_launch_enqueues_when_pool_has_no_capacity():
    service, db, _ = _build_service(
        launch_targets={
            (7, 101): {"requested_app_id": 101, "pool_id": 1, "pool_name": "Pool A"},
        },
        pools=[{"id": 1, "max_concurrent": 1, "is_active": 1}],
        members=[
            {
                "id": 201,
                "pool_id": 1,
                "member_max_concurrent": 1,
                "allowed_users": {7},
                "is_active": True,
            }
        ],
        active_sessions=[
            {
                "session_id": "active-1",
                "user_id": 8,
                "app_id": 201,
                "pool_id": 1,
                "status": "active",
            }
        ],
    )

    result = service.prepare_launch(user_id=7, requested_app_id=101)

    assert result["status"] == "queued"
    assert result["queue_id"] == 1
    assert db.queue_entries[0]["status"] == "queued"
    assert db.queue_entries[0]["user_id"] == 7


def test_prepare_launch_enqueues_when_no_launchable_member_exists():
    service, db, _ = _build_service(
        launch_targets={
            (7, 101): {"requested_app_id": 101, "pool_id": 1, "pool_name": "Pool A"},
        },
        pools=[{"id": 1, "max_concurrent": 2, "is_active": 1}],
        members=[
            {
                "id": 201,
                "pool_id": 1,
                "member_max_concurrent": 1,
                "allowed_users": {7},
                "is_active": True,
            }
        ],
        active_sessions=[
            {
                "session_id": "member-busy",
                "user_id": 8,
                "app_id": 201,
                "pool_id": 1,
                "status": "active",
            }
        ],
    )

    result = service.prepare_launch(user_id=7, requested_app_id=101)

    assert result["status"] == "queued"
    assert result["queue_id"] == 1
    assert db.queue_entries[0]["status"] == "queued"
    assert db.queue_entries[0]["user_id"] == 7


def test_prepare_launch_consumes_ready_queue_entry():
    service, db, _ = _build_service(
        launch_targets={
            (7, 101): {"requested_app_id": 101, "pool_id": 1, "pool_name": "Pool A"},
        },
        pools=[{"id": 1, "max_concurrent": 1, "is_active": 1}],
        members=[
            {
                "id": 201,
                "pool_id": 1,
                "member_max_concurrent": 1,
                "allowed_users": {7},
                "is_active": True,
            }
        ],
        queue_entries=[
            {
                "id": 5,
                "pool_id": 1,
                "user_id": 7,
                "requested_app_id": 101,
                "assigned_app_id": 201,
                "status": "ready",
                "ready_at": datetime(2026, 4, 2, 8, 58, 0),
                "ready_expires_at": datetime(2026, 4, 2, 9, 5, 0),
                "failure_count": 0,
                "last_error": None,
                "cancel_reason": None,
                "created_at": datetime(2026, 4, 2, 8, 57, 0),
            }
        ],
    )

    result = service.prepare_launch(user_id=7, requested_app_id=101, queue_id=5)

    assert result == {
        "status": "started",
        "pool_id": 1,
        "member_app_id": 201,
        "requested_app_name": "Pool A",
        "connection_name": "app_201",
        "queue_id": 5,
    }
    assert db.queue_entries[0]["status"] == "launching"


def test_prepare_launch_invalidates_ready_queue_when_member_unavailable():
    service, db, _ = _build_service(
        launch_targets={
            (7, 101): {"requested_app_id": 101, "pool_id": 1, "pool_name": "Pool A"},
        },
        pools=[{"id": 1, "max_concurrent": 1, "is_active": 1}],
        queue_entries=[
            {
                "id": 5,
                "pool_id": 1,
                "user_id": 7,
                "requested_app_id": 101,
                "assigned_app_id": 999,
                "status": "ready",
                "ready_at": datetime(2026, 4, 2, 8, 58, 0),
                "ready_expires_at": datetime(2026, 4, 2, 9, 5, 0),
                "failure_count": 0,
                "last_error": None,
                "cancel_reason": None,
                "created_at": datetime(2026, 4, 2, 8, 57, 0),
            }
        ],
    )

    result = service.prepare_launch(user_id=7, requested_app_id=101, queue_id=5)

    assert result["status"] == "cancelled"
    assert result["queue_id"] == 5
    assert result["cancel_reason"] == "member_unavailable"
    assert db.queue_entries[0]["status"] == "cancelled"


def test_prepare_launch_invalidates_ready_queue_when_member_pool_drifted():
    service, db, _ = _build_service(
        launch_targets={
            (7, 101): {"requested_app_id": 101, "pool_id": 1, "pool_name": "Pool A"},
        },
        pools=[{"id": 1, "max_concurrent": 1, "is_active": 1}],
        members=[
            {
                "id": 201,
                "pool_id": 2,
                "member_max_concurrent": 1,
                "allowed_users": {7},
                "is_active": True,
            }
        ],
        queue_entries=[
            {
                "id": 6,
                "pool_id": 1,
                "user_id": 7,
                "requested_app_id": 101,
                "assigned_app_id": 201,
                "status": "ready",
                "ready_at": datetime(2026, 4, 2, 8, 58, 0),
                "ready_expires_at": datetime(2026, 4, 2, 9, 5, 0),
                "failure_count": 0,
                "last_error": None,
                "cancel_reason": None,
                "created_at": datetime(2026, 4, 2, 8, 57, 0),
            }
        ],
    )

    result = service.prepare_launch(user_id=7, requested_app_id=101, queue_id=6)

    assert result["status"] == "cancelled"
    assert result["queue_id"] == 6
    assert result["cancel_reason"] == "member_unavailable"
    assert db.queue_entries[0]["status"] == "cancelled"


def test_prepare_launch_invalidates_ready_queue_when_pool_mismatch():
    service, db, _ = _build_service(
        launch_targets={
            (7, 101): {"requested_app_id": 101, "pool_id": 1, "pool_name": "Pool A"},
        },
        pools=[{"id": 1, "max_concurrent": 1, "is_active": 1}],
        queue_entries=[
            {
                "id": 5,
                "pool_id": 2,
                "user_id": 7,
                "requested_app_id": 101,
                "assigned_app_id": 201,
                "status": "ready",
                "ready_at": datetime(2026, 4, 2, 8, 58, 0),
                "ready_expires_at": datetime(2026, 4, 2, 9, 5, 0),
                "failure_count": 0,
                "last_error": None,
                "cancel_reason": None,
                "created_at": datetime(2026, 4, 2, 8, 57, 0),
            }
        ],
    )

    result = service.prepare_launch(user_id=7, requested_app_id=101, queue_id=5)

    assert result["status"] == "cancelled"
    assert result["queue_id"] == 5
    assert result["cancel_reason"] == "pool_mismatch"
    assert db.queue_entries[0]["status"] == "cancelled"


def test_expire_ready_entries_marks_only_expired_ready_rows():
    base_now = datetime(2026, 4, 2, 9, 0, 0)
    service, db, _ = _build_service(
        queue_entries=[
            {
                "id": 1,
                "pool_id": 1,
                "user_id": 7,
                "requested_app_id": 101,
                "assigned_app_id": 201,
                "status": "ready",
                "ready_at": base_now - timedelta(minutes=1),
                "ready_expires_at": base_now - timedelta(seconds=1),
                "cancel_reason": None,
                "created_at": base_now - timedelta(minutes=2),
            },
            {
                "id": 2,
                "pool_id": 1,
                "user_id": 7,
                "requested_app_id": 102,
                "assigned_app_id": 202,
                "status": "ready",
                "ready_at": base_now - timedelta(minutes=1),
                "ready_expires_at": base_now + timedelta(minutes=1),
                "cancel_reason": None,
                "created_at": base_now - timedelta(minutes=2),
            },
            {
                "id": 3,
                "pool_id": 2,
                "user_id": 8,
                "requested_app_id": 103,
                "assigned_app_id": 203,
                "status": "queued",
                "ready_at": None,
                "ready_expires_at": base_now - timedelta(seconds=1),
                "cancel_reason": None,
                "created_at": base_now - timedelta(minutes=2),
            },
        ],
    )

    expired = service.expire_ready_entries(pool_id=1)

    assert expired == [1]
    assert db.queue_entries[0]["status"] == "expired"
    assert db.queue_entries[0]["cancel_reason"] == "timeout"
    assert db.queue_entries[1]["status"] == "ready"
    assert db.queue_entries[2]["status"] == "queued"


def test_cancel_queue_marks_entry_cancelled_for_user():
    service, db, _ = _build_service(
        queue_entries=[
            {
                "id": 3,
                "pool_id": 1,
                "user_id": 7,
                "requested_app_id": 101,
                "assigned_app_id": None,
                "status": "queued",
                "ready_at": None,
                "ready_expires_at": None,
                "cancel_reason": None,
                "created_at": datetime(2026, 4, 2, 8, 55, 0),
            }
        ],
    )

    result = service.cancel_queue(queue_id=3, user_id=7)

    assert result["status"] == "cancelled"
    assert result["cancel_reason"] == "user"
    assert db.queue_entries[0]["status"] == "cancelled"
    assert db.queue_entries[0]["cancel_reason"] == "user"


def test_requeue_after_launch_failure_restores_queue_and_tracks_error():
    base_now = datetime(2026, 4, 2, 9, 0, 0)
    service, db, _ = _build_service(
        queue_entries=[
            {
                "id": 7,
                "pool_id": 1,
                "user_id": 7,
                "requested_app_id": 101,
                "assigned_app_id": 201,
                "status": "launching",
                "ready_at": base_now,
                "ready_expires_at": base_now + timedelta(minutes=1),
                "failure_count": 0,
                "last_error": None,
                "cancel_reason": None,
                "created_at": base_now - timedelta(minutes=1),
            }
        ],
    )

    service.requeue_after_launch_failure(queue_id=7, last_error="boom")

    assert db.queue_entries[0]["status"] == "queued"
    assert db.queue_entries[0]["failure_count"] == 1
    assert db.queue_entries[0]["last_error"] == "boom"


def test_requeue_after_launch_failure_cancels_when_ready_at_missing():
    service, db, _ = _build_service(
        queue_entries=[
            {
                "id": 8,
                "pool_id": 1,
                "user_id": 7,
                "requested_app_id": 101,
                "assigned_app_id": 201,
                "status": "launching",
                "ready_at": None,
                "ready_expires_at": None,
                "failure_count": 0,
                "last_error": None,
                "cancel_reason": None,
                "created_at": datetime(2026, 4, 2, 8, 55, 0),
            }
        ],
    )

    service.requeue_after_launch_failure(queue_id=8, last_error="boom")

    assert db.queue_entries[0]["status"] == "cancelled"
    assert db.queue_entries[0]["cancel_reason"] == "launch_failed"


def test_dispatch_ready_entries_skips_invalid_head_and_advances_next_queue():
    base_now = datetime(2026, 4, 2, 9, 0, 0)
    service, db, _ = _build_service(
        pools=[
            {
                "id": 1,
                "max_concurrent": 2,
                "is_active": 1,
                "auto_dispatch_enabled": 1,
                "dispatch_grace_seconds": 120,
            }
        ],
        members=[
            {
                "id": 301,
                "pool_id": 1,
                "member_max_concurrent": 1,
                "allowed_users": {8},
                "is_active": True,
            }
        ],
        queue_entries=[
            {
                "id": 1,
                "pool_id": 1,
                "user_id": 7,
                "requested_app_id": 101,
                "assigned_app_id": None,
                "status": "queued",
                "ready_at": None,
                    "ready_expires_at": None,
                    "failure_count": 0,
                    "last_error": None,
                    "cancel_reason": None,
                    "created_at": base_now - timedelta(minutes=2),
                },
                {
                    "id": 2,
                "pool_id": 1,
                "user_id": 8,
                "requested_app_id": 102,
                "assigned_app_id": None,
                "status": "queued",
                "ready_at": None,
                    "ready_expires_at": None,
                    "failure_count": 0,
                    "last_error": None,
                    "cancel_reason": None,
                    "created_at": base_now - timedelta(minutes=1),
                },
            ],
        )

    moved = service.dispatch_ready_entries()

    assert moved == [2]
    assert db.queue_entries[0]["status"] == "cancelled"
    assert db.queue_entries[0]["cancel_reason"] == "member_unavailable"
    assert db.queue_entries[1]["status"] == "ready"
    assert db.queue_entries[1]["assigned_app_id"] == 301
    assert db.queue_entries[1]["ready_expires_at"] == base_now + timedelta(seconds=120)


def test_cleanup_invalid_queue_entries_cancels_config_changed_rows():
    base_now = datetime(2026, 4, 2, 9, 0, 0)
    service, db, _ = _build_service(
        launch_targets={
            (7, 101): {"requested_app_id": 101, "pool_id": 2, "pool_name": "Pool B"},
        },
        queue_entries=[
            {
                "id": 11,
                "pool_id": 1,
                "user_id": 7,
                "requested_app_id": 101,
                "assigned_app_id": None,
                "status": "queued",
                "ready_at": None,
                    "ready_expires_at": None,
                    "failure_count": 0,
                    "last_error": None,
                    "cancel_reason": None,
                    "created_at": base_now,
                }
            ],
        )

    cancelled = service.cleanup_invalid_queue_entries(user_id=7)

    assert cancelled == [11]
    assert db.queue_entries[0]["status"] == "cancelled"
    assert db.queue_entries[0]["cancel_reason"] == "config_changed"


def test_cleanup_invalid_queue_entries_cancels_member_unavailable_rows():
    base_now = datetime(2026, 4, 2, 9, 0, 0)
    service, db, _ = _build_service(
        launch_targets={
            (7, 101): {"requested_app_id": 101, "pool_id": 1, "pool_name": "Pool A"},
        },
        members=[
            {
                "id": 301,
                "pool_id": 1,
                "member_max_concurrent": 1,
                "allowed_users": {7},
                "is_active": True,
            }
        ],
        queue_entries=[
            {
                "id": 12,
                "pool_id": 1,
                "user_id": 7,
                    "requested_app_id": 101,
                    "assigned_app_id": 999,
                    "status": "ready",
                    "ready_at": base_now,
                    "ready_expires_at": base_now + timedelta(minutes=1),
                    "failure_count": 0,
                    "last_error": None,
                    "cancel_reason": None,
                    "created_at": base_now,
                }
            ],
        )

    cancelled = service.cleanup_invalid_queue_entries(user_id=7)

    assert cancelled == [12]
    assert db.queue_entries[0]["status"] == "cancelled"
    assert db.queue_entries[0]["cancel_reason"] == "member_unavailable"
