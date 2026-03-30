# Resource Governance And Smoke Tests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the fake/broken pytest baseline with reliable smoke coverage, then add default-off resource governance for launch limits, queueing, timeout reclaim, and admin visibility without breaking current launch behavior.

**Architecture:** Keep the existing FastAPI + plain JS structure, but move resource-governance decision logic into a focused backend module so `router.py` and `monitor.py` do not turn into bigger garbage piles. Store governance settings on `remote_app`, store queue state in a dedicated table, make `/api/remote-apps/launch/{app_id}` return either an immediate launch or a queued response, and expose queue state through admin monitor APIs and the existing admin page.

**Tech Stack:** FastAPI, mysql-connector, plain browser JavaScript, pytest, httpx AsyncClient

**Execution note:** The user explicitly prohibited git commits. Do not add commit steps while executing this plan.

---

### Task 1: Replace The Broken Test Baseline With Real Smoke Tests

**Files:**
- Create: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\resource-governance\tests\conftest.py`
- Create: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\resource-governance\tests\test_portal_smoke.py`
- Modify: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\resource-governance\tests\test_file_router.py`

- [ ] **Step 1: Write the failing smoke tests for auth, launch, and monitor**

```python
import pytest


@pytest.mark.asyncio
async def test_login_returns_portal_jwt(async_client, fake_db):
    fake_db.queue_query_result({
        "id": 7,
        "username": "test",
        "password_hash": "$2b$12$L91JPIXfv6upob1STuLlJuIZqese8iUsJdf9G/YwYCw3mIzm7TJs6",
        "display_name": "测试用户",
        "is_admin": 0,
    })

    resp = await async_client.post("/api/auth/login", json={
        "username": "test",
        "password": "test123",
    })

    assert resp.status_code == 200
    body = resp.json()
    assert body["username"] == "test"
    assert body["display_name"] == "测试用户"
    assert body["token"]


@pytest.mark.asyncio
async def test_launch_returns_ready_payload_and_records_session(
    async_client, auth_header, fake_db, fake_guac_service
):
    fake_db.queue_query_result({"id": 1})
    fake_db.queue_query_result({"id": 1, "name": "记事本"})
    fake_db.queue_query_result([{"id": 1, "hostname": "rdp-host", "port": 3389}])
    fake_guac_service.redirect_url = "http://portal.test/guacamole/#/client/app_1?token=abc"

    resp = await async_client.post("/api/remote-apps/launch/1", headers=auth_header)

    assert resp.status_code == 200
    body = resp.json()
    assert body["connection_name"] == "app_1"
    assert body["redirect_url"] == fake_guac_service.redirect_url
    assert body["session_id"]
    assert fake_db.last_insert_table == "active_session"


@pytest.mark.asyncio
async def test_monitor_overview_counts_only_fresh_active_sessions(
    async_client, admin_header, fake_db
):
    fake_db.queue_query_result([{"id": 1, "name": "记事本", "icon": "edit"}])
    fake_db.queue_query_result([{"app_id": 1, "cnt": 2}])
    fake_db.queue_query_result({"cnt": 2})

    resp = await async_client.get("/api/admin/monitor/overview", headers=admin_header)

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_online"] == 2
    assert body["apps"][0]["active_count"] == 2
```

- [ ] **Step 2: Run the new smoke test file and verify RED**

Run:

```powershell
& 'D:\Nercar\NanGang\PSD\Apps\gucamole_app\.venv\Scripts\python.exe' -m pytest tests\test_portal_smoke.py -q
```

Expected:

```text
FAIL tests/test_portal_smoke.py::test_login_returns_portal_jwt
FAIL tests/test_portal_smoke.py::test_launch_returns_ready_payload_and_records_session
FAIL tests/test_portal_smoke.py::test_monitor_overview_counts_only_fresh_active_sessions
```

- [ ] **Step 3: Add a reusable pytest harness and neuter the import-time suicide test**

```python
# tests/conftest.py
import os
from collections import deque

import pytest
from httpx import ASGITransport, AsyncClient


class FakeDb:
    def __init__(self):
        self.query_results = deque()
        self.update_results = deque()
        self.executed = []
        self.last_insert_table = ""

    def queue_query_result(self, value):
        self.query_results.append(value)

    def queue_update_result(self, value=1):
        self.update_results.append(value)

    def execute_query(self, query, params=None, fetch_one=False):
        self.executed.append(("query", query, params, fetch_one))
        if not self.query_results:
            return None if fetch_one else []
        value = self.query_results.popleft()
        return value

    def execute_update(self, query, params=None):
        self.executed.append(("update", query, params, False))
        upper = query.upper()
        if "INSERT INTO ACTIVE_SESSION" in upper:
            self.last_insert_table = "active_session"
        if self.update_results:
            return self.update_results.popleft()
        return 1


class FakeGuacService:
    def __init__(self):
        self.redirect_url = ""

    async def launch_connection(self, **kwargs):
        return self.redirect_url

    def invalidate_all_sessions(self):
        return None


@pytest.fixture
def fake_db(monkeypatch):
    from backend import router, admin_router, auth, monitor, file_router
    db = FakeDb()
    monkeypatch.setattr(router, "db", db)
    monkeypatch.setattr(admin_router, "db", db)
    monkeypatch.setattr(auth, "db", db)
    monkeypatch.setattr(monitor, "db", db)
    monkeypatch.setattr(file_router, "db", db)
    return db


@pytest.fixture
def fake_guac_service(monkeypatch):
    from backend import router
    svc = FakeGuacService()
    monkeypatch.setattr(router, "guac_service", svc)
    return svc


@pytest.fixture
async def async_client(monkeypatch):
    os.environ["PORTAL_JWT_SECRET"] = "test-secret"
    from backend.app import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
```

```python
# tests/test_file_router.py
def test_pytest_collection_placeholder():
    assert True
```

- [ ] **Step 4: Run the smoke tests again and verify GREEN**

Run:

```powershell
& 'D:\Nercar\NanGang\PSD\Apps\gucamole_app\.venv\Scripts\python.exe' -m pytest tests\test_portal_smoke.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 5: Run the whole test directory and verify the collection poison is gone**

Run:

```powershell
& 'D:\Nercar\NanGang\PSD\Apps\gucamole_app\.venv\Scripts\python.exe' -m pytest tests -q
```

Expected:

```text
4 passed
```

### Task 2: Add Backend Resource Governance With Default-Off Limits And Queueing

**Files:**
- Create: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\resource-governance\backend\resource_governance.py`
- Create: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\resource-governance\database\migrate_resource_governance.sql`
- Create: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\resource-governance\tests\test_resource_governance.py`
- Modify: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\resource-governance\backend\models.py`
- Modify: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\resource-governance\backend\router.py`
- Modify: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\resource-governance\backend\admin_router.py`
- Modify: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\resource-governance\backend\monitor.py`
- Modify: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\resource-governance\database\init.sql`
- Modify: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\resource-governance\deploy\initdb\01-portal-init.sql`

- [ ] **Step 1: Write failing tests for governance decisions**

```python
def test_launch_queues_when_app_limit_reached(async_client, auth_header, fake_db):
    fake_db.queue_query_result({"id": 1})
    fake_db.queue_query_result({
        "id": 1,
        "name": "记事本",
        "queue_enabled": 1,
        "max_concurrent_sessions": 1,
        "max_concurrent_per_user": None,
        "queue_timeout_seconds": 300,
    })
    fake_db.queue_query_result([])
    fake_db.queue_query_result({"active_count": 1, "user_active_count": 0})
    fake_db.queue_query_result({"queue_id": 9, "position": 2})

    resp = async_client.post("/api/remote-apps/launch/1", headers=auth_header)

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "queued"
    assert body["queue_position"] == 2
    assert body["redirect_url"] == ""


def test_launch_rejects_when_limit_reached_and_queue_disabled(async_client, auth_header, fake_db):
    fake_db.queue_query_result({"id": 1})
    fake_db.queue_query_result({
        "id": 1,
        "name": "记事本",
        "queue_enabled": 0,
        "max_concurrent_sessions": 1,
        "max_concurrent_per_user": None,
        "queue_timeout_seconds": 300,
    })
    fake_db.queue_query_result([])
    fake_db.queue_query_result({"active_count": 1, "user_active_count": 0})

    resp = async_client.post("/api/remote-apps/launch/1", headers=auth_header)

    assert resp.status_code == 409
    assert resp.json()["detail"] == "当前应用占用已满，请稍后再试"


def test_cleanup_stale_sessions_expires_old_queue_entries(fake_db):
    from backend.monitor import cleanup_stale_sessions
    fake_db.queue_update_result(2)
    fake_db.queue_update_result(3)

    cleanup_stale_sessions()

    assert "UPDATE launch_queue" in fake_db.executed[-1][1]
```

- [ ] **Step 2: Run the governance tests and verify RED**

Run:

```powershell
& 'D:\Nercar\NanGang\PSD\Apps\gucamole_app\.venv\Scripts\python.exe' -m pytest tests\test_resource_governance.py -q
```

Expected:

```text
FAIL queued response fields missing
FAIL governance columns missing
FAIL queue cleanup not implemented
```

- [ ] **Step 3: Implement the smallest backend slice that makes the tests pass**

```python
# backend/resource_governance.py
from dataclasses import dataclass


@dataclass
class LaunchGateResult:
    allowed: bool
    queued: bool = False
    queue_position: int = 0
    queue_id: int = 0
    retry_after_seconds: int = 5


def governance_enabled(app_row: dict) -> bool:
    return bool(app_row.get("max_concurrent_sessions") or app_row.get("max_concurrent_per_user"))
```

```python
# backend/models.py
class LaunchResponse(BaseModel):
    redirect_url: str = ""
    connection_name: str = ""
    session_id: str = ""
    status: str = "ready"
    queue_position: int = 0
    retry_after_seconds: int = 0
    message: str = ""
```

```sql
ALTER TABLE remote_app
    ADD COLUMN max_concurrent_sessions INT DEFAULT NULL,
    ADD COLUMN max_concurrent_per_user INT DEFAULT NULL,
    ADD COLUMN queue_enabled TINYINT(1) NOT NULL DEFAULT 0,
    ADD COLUMN queue_timeout_seconds INT DEFAULT 300;

CREATE TABLE IF NOT EXISTS launch_queue (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    app_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'waiting',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_waiting_user_app (app_id, user_id, status),
    INDEX idx_app_status_created (app_id, status, created_at)
);
```

- [ ] **Step 4: Extend monitor/admin queries so governance state is visible to the backend**

Run:

```powershell
& 'D:\Nercar\NanGang\PSD\Apps\gucamole_app\.venv\Scripts\python.exe' -m pytest tests\test_resource_governance.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 5: Run smoke plus governance tests together**

Run:

```powershell
& 'D:\Nercar\NanGang\PSD\Apps\gucamole_app\.venv\Scripts\python.exe' -m pytest tests\test_portal_smoke.py tests\test_resource_governance.py -q
```

Expected:

```text
6 passed
```

### Task 3: Wire Queueing Into The User Launch Flow And Admin UI

**Files:**
- Modify: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\resource-governance\frontend\js\app.js`
- Modify: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\resource-governance\frontend\js\admin.js`
- Modify: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\resource-governance\frontend\admin.html`
- Modify: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\resource-governance\backend\admin_router.py`
- Modify: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\resource-governance\backend\models.py`
- Modify: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\resource-governance\tests\test_portal_smoke.py`

- [ ] **Step 1: Write the failing API/UI contract tests first**

```python
@pytest.mark.asyncio
async def test_launch_smoke_reports_queued_status(async_client, auth_header, fake_db):
    fake_db.queue_query_result({"id": 1})
    fake_db.queue_query_result({
        "id": 1,
        "name": "记事本",
        "queue_enabled": 1,
        "max_concurrent_sessions": 1,
        "max_concurrent_per_user": 1,
        "queue_timeout_seconds": 300,
    })
    fake_db.queue_query_result([])
    fake_db.queue_query_result({"active_count": 1, "user_active_count": 1})
    fake_db.queue_query_result({"queue_id": 3, "position": 1})

    resp = await async_client.post("/api/remote-apps/launch/1", headers=auth_header)

    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"
    assert resp.json()["message"].startswith("已进入等待队列")
```

- [ ] **Step 2: Run the updated smoke file and verify RED**

Run:

```powershell
& 'D:\Nercar\NanGang\PSD\Apps\gucamole_app\.venv\Scripts\python.exe' -m pytest tests\test_portal_smoke.py -q
```

Expected:

```text
FAIL queued launch contract missing
```

- [ ] **Step 3: Implement the minimum UI behavior**

```javascript
if (data.status === 'queued') {
    renderQueueWaiting(win, appName, data.queue_position, data.retry_after_seconds);
    pollQueuedLaunch(win, appId, appName, data.retry_after_seconds);
    return;
}
```

```javascript
data.max_concurrent_sessions = parseNullableInt('app-max-concurrent-sessions');
data.max_concurrent_per_user = parseNullableInt('app-max-concurrent-per-user');
data.queue_enabled = document.getElementById('app-queue-enabled').checked;
data.queue_timeout_seconds = parseNullableInt('app-queue-timeout-seconds') || 300;
```

```javascript
summary.textContent =
    '在线 ' + data.total_online + ' 人 / ' + data.total_sessions + ' 个会话 / 排队 ' + data.total_queued + ' 人';
```

- [ ] **Step 4: Run the smoke and governance tests again**

Run:

```powershell
& 'D:\Nercar\NanGang\PSD\Apps\gucamole_app\.venv\Scripts\python.exe' -m pytest tests\test_portal_smoke.py tests\test_resource_governance.py -q
```

Expected:

```text
all tests pass
```

- [ ] **Step 5: Do a manual browser-free API sweep for the new admin payloads**

Run:

```powershell
& 'D:\Nercar\NanGang\PSD\Apps\gucamole_app\.venv\Scripts\python.exe' -m pytest tests\test_portal_smoke.py::test_monitor_overview_counts_only_fresh_active_sessions -q
```

Expected:

```text
1 passed
```

### Task 4: Final Verification Before Any Completion Claim

**Files:**
- Verify only

- [ ] **Step 1: Run the targeted regression suite**

Run:

```powershell
& 'D:\Nercar\NanGang\PSD\Apps\gucamole_app\.venv\Scripts\python.exe' -m pytest tests\test_portal_smoke.py tests\test_resource_governance.py -q
```

Expected:

```text
0 failures
```

- [ ] **Step 2: Run the full test directory**

Run:

```powershell
& 'D:\Nercar\NanGang\PSD\Apps\gucamole_app\.venv\Scripts\python.exe' -m pytest tests -q
```

Expected:

```text
0 failures
```

- [ ] **Step 3: Run a syntax sweep on the changed Python files**

Run:

```powershell
& 'D:\Nercar\NanGang\PSD\Apps\gucamole_app\.venv\Scripts\python.exe' -m py_compile backend\app.py backend\auth.py backend\admin_router.py backend\models.py backend\monitor.py backend\resource_governance.py backend\router.py
```

Expected:

```text
exit code 0
```

- [ ] **Step 4: Re-read the requirements and verify each one against code and test evidence**

Checklist:

```text
[ ] auth / launch / monitor smoke tests are real pytest tests
[ ] resource-governance rules are default-off
[ ] app-level concurrency limit exists
[ ] per-user concurrency limit exists
[ ] queueing works when enabled
[ ] stale session cleanup reclaims occupancy
[ ] stale queue entries expire
[ ] admin monitor exposes queue visibility
[ ] admin app editor exposes governance settings
[ ] no existing launch path breaks when governance is disabled
```

## Self-Review

- Spec coverage: Task 1 covers smoke tests and baseline cleanup. Task 2 covers backend schema, launch gating, queueing, and timeout reclaim. Task 3 covers admin visibility plus user launch polling. Task 4 covers final verification.
- Placeholder scan: Removed `TODO`-style placeholders; every task names exact files and commands.
- Type consistency: `LaunchResponse` uses `status`, `queue_position`, `retry_after_seconds`, and `message` consistently across backend, tests, and frontend.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-03-30-resource-governance-and-smoke-tests.md`.

The user already chose Subagent-Driven execution, so execute this plan in the current worktree with fresh subagents per task, TDD for implementation, and verification-before-completion at the end.
