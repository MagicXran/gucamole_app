# Vue3 Admin Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Do **not** commit during execution because this repo's instructions forbid unrequested commits.

**Goal:** Migrate the system-management workbench into the Vue3 portal shell so admins can operate App management, queue scheduling, and resource monitoring from `/portal/` without breaking the existing plain-JS admin console.

**Architecture:** Keep backend permission enforcement on the current FastAPI admin endpoints and expose the Vue admin area only for authenticated admins via session bootstrap menu/capability data. Reuse existing `/api/admin/apps`, `/api/admin/pools`, `/api/admin/pools/{pool_id}/attachments`, `/api/admin/pools/queues`, `/api/admin/monitor/*`, and `/api/admin/workers/*` contracts wherever they already fit, and add only the missing backend tests or tiny compatibility fixes needed for truthful UI behavior and legacy admin safety.

**Tech Stack:** Vue 3, Vue Router, Pinia, Axios, Vitest, FastAPI, pytest, existing plain JS admin shell, Node `--test`.

---

### Task 1: Add admin session/navigation gating and Vue route shell

**Files:**
- Modify: `backend/identity_access.py`
- Modify: `tests/test_session_bootstrap.py`
- Create: `portal_ui/src/modules/admin/routes.ts`
- Create: `portal_ui/src/modules/admin/views/AdminDashboardView.vue`
- Modify: `portal_ui/src/router/index.ts`
- Modify: `portal_ui/src/stores/navigation.ts`
- Create: `portal_ui/tests/unit/admin-navigation.spec.ts`

- [ ] **Step 1: Write the failing backend bootstrap test**
  - Cover:
    - admin session bootstrap includes an `admin` menu group only for `is_admin = true`
    - regular users still do **not** receive any admin menu entry
    - compute remains the default landing group even when admin routes exist
    - frontend-facing capability data contains only what Vue needs for menu/action pruning, not backend trust

- [ ] **Step 2: Run the backend bootstrap test to verify it fails**
  - Run: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\.venv\Scripts\python.exe -m pytest tests\test_session_bootstrap.py -q`
  - Expected: FAIL because admin menu/capability data is not emitted yet.

- [ ] **Step 3: Write the failing Vue navigation test**
  - Cover:
    - `PortalSidebar` renders `系统管理` only for admins
    - `/admin` and its child routes register in the Vue router
    - breadcrumb resolution works for `/admin/apps`, `/admin/queues`, `/admin/monitor`, `/admin/workers`
    - default route stays on compute, not `/admin`

- [ ] **Step 4: Run the Vue navigation test to verify it fails**
  - Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm run test -- admin-navigation.spec.ts`
  - Expected: FAIL because the admin Vue module and routes do not exist.

- [ ] **Step 5: Implement the minimal admin shell foundation**
  - Extend session bootstrap menu/capability shaping in `backend/identity_access.py`.
  - Add `portal_ui/src/modules/admin/routes.ts` with:
    - `/admin`
    - `/admin/apps`
    - `/admin/queues`
    - `/admin/monitor`
    - `/admin/workers`
  - Add `AdminDashboardView.vue` as a real landing page with links/cards into the four admin areas.
  - Keep menu/action pruning in Vue only; backend still enforces `require_admin`.

- [ ] **Step 6: Run the targeted backend and Vue tests to verify they pass**
  - Re-run:
    - `D:\Nercar\NanGang\PSD\Apps\gucamole_app\.venv\Scripts\python.exe -m pytest tests\test_session_bootstrap.py -q`
    - `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm run test -- admin-navigation.spec.ts`
  - Expected: PASS.

### Task 2: Build Vue App management with `app_kind` and pool attachments

**Files:**
- Create: `portal_ui/src/modules/admin/types/apps.ts`
- Create: `portal_ui/src/modules/admin/services/api/apps.ts`
- Create: `portal_ui/src/modules/admin/stores/apps.ts`
- Create: `portal_ui/src/modules/admin/components/AdminPoolAttachmentsEditor.vue`
- Create: `portal_ui/src/modules/admin/components/AdminAppFormDialog.vue`
- Create: `portal_ui/src/modules/admin/views/AdminAppsView.vue`
- Create: `portal_ui/tests/unit/admin-apps-view.spec.ts`
- Modify: `frontend/js/admin-app-modal-ui.js`
- Modify: `tests/test_admin_app_transfer_controls.mjs`
- Modify: `tests/test_router_drive_transfer_policy.py`
- Modify: `tests/test_admin_pool_attachment_router.py`

- [ ] **Step 1: Write the failing backend admin-app tests**
  - Cover:
    - create/update app keeps `app_kind`
    - pool attachment read/write contracts stay unchanged
    - legacy plain-JS attachment editor reports malformed line input with a user-visible error instead of silent promise rejection

- [ ] **Step 2: Run the failing backend + Node tests**
  - Run:
    - `D:\Nercar\NanGang\PSD\Apps\gucamole_app\.venv\Scripts\python.exe -m pytest tests\test_router_drive_transfer_policy.py tests\test_admin_pool_attachment_router.py -q`
    - `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation; node --test tests\test_admin_app_transfer_controls.mjs`
  - Expected: FAIL because malformed attachment input is not surfaced cleanly and Vue admin app management does not exist yet.

- [ ] **Step 3: Write the failing Vue App-management tests**
  - Cover:
    - admin app list loads from `/api/admin/apps`
    - dialog supports create/edit with real `app_kind` field
    - dialog loads pools, worker groups, script profiles, and current pool attachments
    - saving attachments uses `/api/admin/pools/{pool_id}/attachments`
    - action buttons are hidden/disabled for non-admin session state

- [ ] **Step 4: Run the Vue App-management tests to verify they fail**
  - Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm run test -- admin-apps-view.spec.ts`
  - Expected: FAIL because the Vue App management module does not exist.

- [ ] **Step 5: Implement the minimal App-management module**
  - Add typed API/service/store wrappers for:
    - app list/create/update/delete
    - pool list
    - pool attachment get/replace
    - worker-group list
    - script-profile list
  - Build `AdminAppsView.vue` with a truthful table and create/edit/delete actions.
  - Build `AdminAppFormDialog.vue` with `app_kind` and pool-level attachment editing via `AdminPoolAttachmentsEditor.vue`.
  - Patch `frontend/js/admin-app-modal-ui.js` only enough to surface malformed attachment lines without breaking current admin behavior or Node tests.

- [ ] **Step 6: Run the targeted tests to verify they pass**
  - Re-run:
    - `D:\Nercar\NanGang\PSD\Apps\gucamole_app\.venv\Scripts\python.exe -m pytest tests\test_router_drive_transfer_policy.py tests\test_admin_pool_attachment_router.py -q`
    - `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation; node --test tests\test_admin_app_transfer_controls.mjs`
    - `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm run test -- admin-apps-view.spec.ts`
  - Expected: PASS.

### Task 3: Build queue scheduling, monitor, and worker Vue pages

**Files:**
- Create: `portal_ui/src/modules/admin/types/ops.ts`
- Create: `portal_ui/src/modules/admin/services/api/ops.ts`
- Create: `portal_ui/src/modules/admin/stores/queues.ts`
- Create: `portal_ui/src/modules/admin/stores/monitor.ts`
- Create: `portal_ui/src/modules/admin/stores/workers.ts`
- Create: `portal_ui/src/modules/admin/views/AdminQueuesView.vue`
- Create: `portal_ui/src/modules/admin/views/AdminMonitorView.vue`
- Create: `portal_ui/src/modules/admin/views/AdminWorkersView.vue`
- Create: `portal_ui/tests/unit/admin-queues-view.spec.ts`
- Create: `portal_ui/tests/unit/admin-monitor-view.spec.ts`
- Create: `portal_ui/tests/unit/admin-workers-view.spec.ts`
- Create: `tests/test_admin_worker_router.py`
- Modify: `tests/test_admin_pool_router.py`
- Modify: `tests/test_monitor_reclaim.py`

- [ ] **Step 1: Write the failing backend admin-ops tests**
  - Cover:
    - admin queue list returns truthful queue rows
    - admin queue cancel endpoint cancels only live queue entries
    - admin monitor overview/sessions stay stable for the Vue monitor page
    - admin worker group/node list endpoints return the shapes the Vue page needs

- [ ] **Step 2: Run the failing backend tests**
  - Run: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\.venv\Scripts\python.exe -m pytest tests\test_admin_pool_router.py tests\test_monitor_reclaim.py tests\test_admin_worker_router.py -q`
  - Expected: FAIL because worker-route coverage is missing and queue/monitor contracts are not yet locked for the Vue admin module.

- [ ] **Step 3: Write the failing Vue admin-ops tests**
  - Cover:
    - `AdminQueuesView` renders queue rows and can cancel queue items
    - `AdminMonitorView` renders overview cards and active session table with reclaim action
    - `AdminWorkersView` renders group/node lists and exposes truthful worker actions
    - non-admin session state does not expose these actions

- [ ] **Step 4: Run the Vue admin-ops tests to verify they fail**
  - Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm run test -- admin-queues-view.spec.ts admin-monitor-view.spec.ts admin-workers-view.spec.ts`
  - Expected: FAIL because the Vue admin ops pages do not exist.

- [ ] **Step 5: Implement the minimal admin-ops module**
  - Add typed services/stores for queues, monitor, and workers.
  - Build:
    - `AdminQueuesView.vue` for queue rows, status, and cancel action
    - `AdminMonitorView.vue` for overview cards and session list
    - `AdminWorkersView.vue` for group/node status and existing worker actions
  - Reuse existing backend endpoints; do not invent a fake analytics layer.

- [ ] **Step 6: Run the targeted backend and Vue tests to verify they pass**
  - Re-run:
    - `D:\Nercar\NanGang\PSD\Apps\gucamole_app\.venv\Scripts\python.exe -m pytest tests\test_admin_pool_router.py tests\test_monitor_reclaim.py tests\test_admin_worker_router.py -q`
    - `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm run test -- admin-queues-view.spec.ts admin-monitor-view.spec.ts admin-workers-view.spec.ts`
  - Expected: PASS.

### Task 4: Integrate the admin workbench and run full Phase 8 verification

**Files:**
- Modify: `portal_ui/src/modules/admin/routes.ts`
- Modify: `portal_ui/src/modules/admin/views/AdminDashboardView.vue`
- Modify: any admin store/view files from Tasks 1-3 as needed
- No backend scope expansion beyond tests/fixes from Tasks 1-3 unless verification proves it necessary

- [ ] **Step 1: Run the phase-targeted backend verification**
  - Run: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\.venv\Scripts\python.exe -m pytest tests\test_session_bootstrap.py tests\test_router_drive_transfer_policy.py tests\test_admin_pool_attachment_router.py tests\test_admin_pool_router.py tests\test_monitor_reclaim.py tests\test_admin_worker_router.py -q`
  - Expected: PASS.

- [ ] **Step 2: Run required Node verification**
  - Run:
    - `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation; node --test tests\test_admin_app_transfer_controls.mjs`
    - `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation; node --test tests\test_portal_dockerfile_build.mjs`
  - Expected: PASS.

- [ ] **Step 3: Run full Vue verification**
  - Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui && npm run test && npm run typecheck && npm run build`
  - Expected: PASS.

- [ ] **Step 4: Run broader backend sanity verification**
  - Run: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\.venv\Scripts\python.exe -m pytest`
  - Expected: Known failure remains `tests/test_file_router.py` because of the pre-existing `ASGITransport.handle_request` + `sys.exit(1)` issue. Do **not** misattribute that to Phase 8.

- [ ] **Step 5: Request final code review**
  - Run a final spec review and code-quality review for the full Phase 8 diff.
  - If either review finds Critical or Important issues, fix them before calling the phase complete.

---

## Self-Review

- **Spec coverage:** This plan covers the three required admin slices: App management (`app_kind` + pool attachments), queue scheduling, and resource/worker monitoring, plus admin-only menu gating and mandatory verification.
- **Placeholder scan:** No TBD/TODO placeholders remain.
- **Type consistency:** Vue admin pages all consume the existing `/api/admin/*` contracts instead of inventing a second backend shape; legacy plain-JS admin remains in place.
- **Scope choice:** This phase does **not** jump to stats/comments. That work stays in Phase 9 where it belongs.
