# Transfer Policy And File Refresh Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the unfinished Guacamole transfer-policy work end to end and replace the crude fixed file polling with an adaptive refresh loop that is more responsive without wasting backend scans.

**Architecture:** Keep the portal direct. Model Guacamole upload/download controls as nullable per-app overrides (`NULL=inherit global`, `1=force disable`, `0=force allow`) so existing global defaults remain authoritative until an app explicitly overrides them. For file refresh, keep HTTP polling but move from fixed `setInterval()` to a self-scheduled loop that speeds up after observed mutations and backs off when stable.

**Tech Stack:** FastAPI, mysql-connector, plain browser JavaScript, Node test runner, pytest

---

### Task 1: Close Guacamole transfer-policy tri-state end to end

**Files:**
- Modify: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\tests\test_router_drive_transfer_policy.py`
- Modify: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\tests\test_admin_app_transfer_controls.mjs`
- Modify: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\backend\models.py`
- Modify: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\backend\admin_router.py`
- Modify: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\backend\router.py`
- Modify: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\frontend\js\admin.js`
- Modify: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\database\init.sql`
- Modify: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\deploy\initdb\01-portal-init.sql`
- Modify: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\scripts\verify_portal_schema.py`
- Create: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\database\migrate_transfer_policy_tristate.sql`

- [ ] **Step 1: Write the failing tests**

```python
def test_build_all_connections_inherits_global_transfer_disable_flags():
    router_module = _load_router_module(None, None)
    params = router_module._build_all_connections(7)["app_1"]["parameters"]
    assert params["disable-download"] == "true"
    assert params["disable-upload"] == "true"


def test_build_all_connections_allows_per_app_transfer_override():
    router_module = _load_router_module(0, 0)
    params = router_module._build_all_connections(7)["app_1"]["parameters"]
    assert "disable-download" not in params
    assert "disable-upload" not in params
```

```javascript
test('admin app modal exposes transfer override controls', () => {
  assert.match(source, /app-disable-download/);
  assert.match(source, /app-disable-upload/);
  assert.match(source, /浏览器下载通道/);
  assert.match(source, /浏览器上传通道/);
});

test('admin saveApp sends transfer override payload keys', () => {
  assert.match(source, /disable_download\\s*:/);
  assert.match(source, /disable_upload\\s*:/);
});
```

- [ ] **Step 2: Run the failing tests and capture the red state**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_router_drive_transfer_policy.py -q`
Expected: `test_build_all_connections_allows_per_app_transfer_override` fails because router only uses global flags.

Run: `node --test tests/test_admin_app_transfer_controls.mjs`
Expected: both tests fail because the admin modal and payload do not expose transfer controls.

- [ ] **Step 3: Implement nullable tri-state storage and resolution**

```python
# backend/router.py
def _resolve_transfer_disable(global_disabled: bool, app_override):
    if app_override is None:
        return bool(global_disabled)
    return bool(app_override)


query = """
    SELECT ..., a.disable_download, a.disable_upload
    FROM remote_app a
    ...
"""

disable_download = _resolve_transfer_disable(
    drive_disable_download,
    app.get("disable_download"),
)
disable_upload = _resolve_transfer_disable(
    drive_disable_upload,
    app.get("disable_upload"),
)
```

```python
# backend/models.py
disable_download: Optional[bool] = None
disable_upload: Optional[bool] = None
```

```python
# backend/admin_router.py
"disable_download": None if req.disable_download is None else (1 if req.disable_download else 0),
"disable_upload": None if req.disable_upload is None else (1 if req.disable_upload else 0),
```

```sql
ALTER TABLE remote_app
    MODIFY disable_download TINYINT(1) NULL DEFAULT NULL,
    MODIFY disable_upload TINYINT(1) NULL DEFAULT NULL;

UPDATE remote_app
SET disable_download = NULL
WHERE disable_download = 0;

UPDATE remote_app
SET disable_upload = NULL
WHERE disable_upload = 0;
```

- [ ] **Step 4: Implement admin tri-state controls without adding junk**

```javascript
function triStateOptions(selectedValue) {
  return [
    { value: '', label: '继承全局' },
    { value: 'true', label: '强制禁用' },
    { value: 'false', label: '强制允许' },
  ];
}

disable_download: readTriState('app-disable-download'),
disable_upload: readTriState('app-disable-upload'),
```

The modal must use `select` controls with ids `app-disable-download` and `app-disable-upload`. Default to `继承全局`. Do not silently coerce `null` to `false`.

- [ ] **Step 5: Re-run task-specific verification**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_router_drive_transfer_policy.py -q`
Expected: `2 passed`

Run: `node --test tests/test_admin_app_transfer_controls.mjs`
Expected: `2 pass`

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_guacamole_crypto.py -q`
Expected: `1 passed`

- [ ] **Step 6: Review compatibility risks before moving on**

Checklist:
- Existing apps with untouched `0` values are migrated to `NULL`, so they continue inheriting the global disable flags.
- `backend/admin_router.py` update logic preserves explicit `null` and does not collapse it into `false`.
- The schema verifier still validates the required columns after the nullable-default change.


### Task 2: Replace fixed file polling with an adaptive refresh loop

**Files:**
- Modify: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\tests\test_portal_file_browser.mjs`
- Modify: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\frontend\js\portal-file-browser.js`
- Modify: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\frontend\js\portal-files.js`
- Modify: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\frontend\js\app.js`
- Modify: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\frontend\js\portal-uploads.js`

- [ ] **Step 1: Write the failing refresh-policy tests**

```javascript
test('resolveRefreshDelay returns fast interval during burst window', () => {
  assert.equal(mod.resolveRefreshDelay({
    nowMs: 25_000,
    fastModeUntilMs: 30_000,
    hasPendingItems: false,
  }), 2000);
});

test('resolveRefreshDelay backs off once the directory is stable', () => {
  assert.equal(mod.resolveRefreshDelay({
    nowMs: 35_000,
    fastModeUntilMs: 30_000,
    hasPendingItems: false,
  }), 10000);
});
```

- [ ] **Step 2: Run the failing test**

Run: `node --test tests/test_portal_file_browser.mjs`
Expected: failure because `resolveRefreshDelay` does not exist yet.

- [ ] **Step 3: Implement adaptive refresh helpers and wire them into the file tab**

```javascript
// frontend/js/portal-file-browser.js
export function resolveRefreshDelay(options) {
  if (options.hasPendingItems) return 2000;
  if (options.nowMs < options.fastModeUntilMs) return 2000;
  return 10000;
}
```

```javascript
// frontend/js/portal-files.js
var _filesRefreshState = {
  timer: 0,
  fastModeUntilMs: 0,
};

function markFilesRefreshBurst(durationMs) {
  _filesRefreshState.fastModeUntilMs = Math.max(
    _filesRefreshState.fastModeUntilMs,
    Date.now() + durationMs
  );
}
```

Use `setTimeout()` scheduling, not nested `setInterval()`. Trigger burst mode when:
- user enters the file tab
- page becomes visible again
- upload/delete/create-folder completes
- file signature changes between polls
- pending-transfer badges are present

- [ ] **Step 4: Keep the loop balanced**

Rules:
- visible file tab + active burst or pending items → 2s
- visible file tab + stable state → 10s
- hidden tab → stop scheduling
- quota refresh remains slower and separate

Do not add WebSocket/SSE. That would be overdesigned nonsense for this portal.

- [ ] **Step 5: Re-run task-specific verification**

Run: `node --test tests/test_portal_file_browser.mjs`
Expected: all tests pass, including the new refresh-delay checks.

- [ ] **Step 6: Smoke-check that upload-driven refresh still works**

Run: `rg -n "loadFiles\\(_currentPath\\)|markFilesRefreshBurst" frontend/js/portal-uploads.js frontend/js/portal-files.js frontend/js/app.js`
Expected: upload completion still triggers an immediate refresh, and the adaptive loop is the only scheduler.


### Task 3: Final verification and review closure

**Files:**
- Review only: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\backend\router.py`
- Review only: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\backend\admin_router.py`
- Review only: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\frontend\js\admin.js`
- Review only: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\frontend\js\portal-files.js`

- [ ] **Step 1: Run the focused verification suite**

Run: `node --test tests/test_admin_app_transfer_controls.mjs tests/test_portal_file_browser.mjs`
Expected: all subtests pass.

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_router_drive_transfer_policy.py tests/test_guacamole_crypto.py tests/test_verify_portal_schema.py -q`
Expected: all tests pass.

- [ ] **Step 2: Run the schema verifier unit test**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_verify_portal_schema.py -q`
Expected: pass, proving the verifier still guards required portal columns.

- [ ] **Step 3: Request code review on the finished diff**

Reviewer scope:
- Transfer policy semantics preserve current global defaults.
- Admin UI exposes only the requested tri-state controls, nothing extra.
- File refresh logic is simpler than before and has no orphan timer path.

- [ ] **Step 4: Fix any review findings, then re-run the same verification commands**

Only after the review comes back clean may the task be considered closed.
