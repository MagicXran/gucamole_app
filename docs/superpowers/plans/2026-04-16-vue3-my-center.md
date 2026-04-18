# Vue3 My Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Do **not** commit during execution because this repo's instructions forbid unrequested commits.

**Goal:** Migrate “我的中心” into the Vue3 portal shell so `个人空间 / App任务 / 预约登记` form a working user-facing loop without falling back to the legacy plain-JS portal.

**Architecture:** Keep the existing Vue shell and `/api/session/bootstrap` as the navigation source of truth, extend the menu tree with a `我的` group, and add a dedicated `portal_ui/src/modules/my/` module set for workspace, tasks, and bookings. Reuse the existing files/tasks APIs wherever they already fit, add only the missing `POST /api/files/move` and independent booking APIs, and keep file-safety / Windows filename restrictions enforced entirely by the backend.

**Tech Stack:** Vue 3, Vue Router, Pinia, Axios, Vitest, FastAPI, pytest, MySQL 8.

---

### Task 1: Extend session navigation for the Vue “我的中心” shell

**Files:**
- Modify: `backend/identity_access.py`
- Modify: `tests/test_session_bootstrap.py`
- Modify: `portal_ui/src/router/index.ts`
- Modify: `portal_ui/src/stores/navigation.ts`
- Modify: `portal_ui/src/shell/PortalSidebar.vue`
- Modify: `portal_ui/src/shell/PortalTopbar.vue`
- Create: `portal_ui/src/modules/my/index.ts`
- Create: `portal_ui/src/modules/my/routes.ts`
- Create: `portal_ui/tests/unit/my-navigation.spec.ts`

- [ ] **Step 1: Write the failing bootstrap/menu tests**
  - Add backend assertions that authenticated users now receive a second top-level `my` menu group with children:
    - `/my/workspace`
    - `/my/tasks`
    - `/my/bookings`
  - Add frontend assertions that Vue navigation renders `我的` and that the topbar exposes current user identity plus a logout entry while keeping the result-center link external.

- [ ] **Step 2: Run the targeted tests to verify they fail**
  - Run: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\.venv\Scripts\python.exe -m pytest tests\test_session_bootstrap.py -q`
  - Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm run test -- my-navigation.spec.ts`
  - Expected: FAIL because the session menu tree and Vue shell do not include `我的` yet.

- [ ] **Step 3: Implement the minimal navigation slice**
  - Extend `MENU_TREE` in `backend/identity_access.py` with a `my` group.
  - Keep `计算资源` first so the default landing page stays stable.
  - Add placeholder route records for `WorkspaceView`, `AppTasksView`, and `BookingRegisterView` under `/my/...`.
  - Update breadcrumb resolution for the three `my` routes.
  - Update `PortalTopbar.vue` to show display name, result-center external link, and logout action without pulling plain-JS portal code into Vue.

- [ ] **Step 4: Run the targeted tests to verify they pass**
  - Re-run the two commands from Step 2.
  - Expected: PASS.

### Task 2: Add the backend file move API with safety guarantees

**Files:**
- Modify: `backend/file_router.py`
- Create: `tests/test_file_move_router.py`

- [ ] **Step 1: Write the failing move tests**
  - Cover:
    - successful move within the same user root
    - rejecting Windows reserved target names
    - rejecting path traversal / moving outside user root
    - rejecting overwrite of an existing target
  - Use a dedicated pytest module instead of touching `tests/test_file_router.py`.

- [ ] **Step 2: Run the targeted tests to verify they fail**
  - Run: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\.venv\Scripts\python.exe -m pytest tests\test_file_move_router.py -q`
  - Expected: FAIL because `/api/files/move` does not exist.

- [ ] **Step 3: Implement the minimal move endpoint**
  - Add a request model with `source_path` and `target_path`.
  - Resolve both paths with `_safe_resolve`.
  - Validate the target filename with `_validate_filename`.
  - Reject root moves, missing sources, and target collisions.
  - Use `shutil.move` only after both resolved paths are proven to be inside the same user root.
  - Invalidate usage cache and write an audit log entry after success.

- [ ] **Step 4: Run the targeted tests to verify they pass**
  - Re-run: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\.venv\Scripts\python.exe -m pytest tests\test_file_move_router.py -q`
  - Expected: PASS.

### Task 3: Build the Vue workspace module (`个人空间`)

**Files:**
- Create: `portal_ui/src/modules/my/views/WorkspaceView.vue`
- Create: `portal_ui/src/modules/my/components/FileBrowser.vue`
- Create: `portal_ui/src/modules/my/services/api/files.ts`
- Create: `portal_ui/src/modules/my/types/files.ts`
- Create: `portal_ui/src/modules/my/stores/workspace.ts`
- Create: `portal_ui/tests/unit/workspace-view.spec.ts`
- Create: `portal_ui/tests/unit/file-browser.spec.ts`

- [ ] **Step 1: Write the failing workspace tests**
  - Cover:
    - directory listing renders from `/api/files/list`
    - toolbar actions trigger mkdir / delete / move
    - selecting a file exposes download action
    - uploading files uses the existing resumable endpoints through a Vue service wrapper
    - clicking an Output-linked path preserves the path in route query for deep-link return

- [ ] **Step 2: Run the targeted tests to verify they fail**
  - Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm run test -- workspace-view.spec.ts file-browser.spec.ts`
  - Expected: FAIL because the Vue module does not exist.

- [ ] **Step 3: Implement the minimal workspace module**
  - Build a focused `workspace` store that owns:
    - current path
    - file items
    - quota overview
    - pending action state
  - Wrap existing file APIs:
    - `GET /api/files/space`
    - `GET /api/files/list`
    - `POST /api/files/mkdir`
    - `DELETE /api/files/file`
    - `POST /api/files/download-token`
    - `POST /api/files/move`
    - resumable upload init/chunk/cancel
  - Keep Output browsing inside the same module; no plain-JS fallback.
  - Add the minimum UI needed for browse/upload/download/delete/move/new-folder.

- [ ] **Step 4: Run the targeted tests to verify they pass**
  - Re-run the command from Step 2.
  - Expected: PASS.

### Task 4: Build the Vue App任务 module

**Files:**
- Create: `portal_ui/src/modules/my/views/AppTasksView.vue`
- Create: `portal_ui/src/modules/my/components/TaskTable.vue`
- Create: `portal_ui/src/modules/my/components/TaskDetailDrawer.vue`
- Create: `portal_ui/src/modules/my/services/api/tasks.ts`
- Create: `portal_ui/src/modules/my/types/tasks.ts`
- Create: `portal_ui/src/modules/my/stores/tasks.ts`
- Create: `portal_ui/tests/unit/app-tasks-view.spec.ts`
- Create: `portal_ui/tests/unit/task-detail-drawer.spec.ts`

- [ ] **Step 1: Write the failing task-module tests**
  - Cover:
    - listing only the current user’s tasks from `GET /api/tasks`
    - client-side filtering by status and name keyword
    - opening task detail, logs, and result index
    - converting Output artifacts into a workspace jump target
    - cancelling only cancellable tasks

- [ ] **Step 2: Run the targeted tests to verify they fail**
  - Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm run test -- app-tasks-view.spec.ts task-detail-drawer.spec.ts`
  - Expected: FAIL because the Vue tasks module does not exist.

- [ ] **Step 3: Implement the minimal task module**
  - Reuse existing endpoints:
    - `GET /api/tasks`
    - `GET /api/tasks/{task_id}`
    - `GET /api/tasks/{task_id}/logs`
    - `GET /api/tasks/{task_id}/artifacts`
    - `POST /api/tasks/{task_id}/cancel`
  - Keep filtering client-side in the Vue store to avoid inventing backend query params that do not yet exist.
  - Make Output artifacts navigate to `/my/workspace?path=...` when `relative_path` points into `Output/`.

- [ ] **Step 4: Run the targeted tests to verify they pass**
  - Re-run the command from Step 2.
  - Expected: PASS.

### Task 5: Add independent booking register APIs and the Vue module

**Files:**
- Create: `backend/booking_router.py`
- Create: `backend/booking_service.py`
- Modify: `backend/models.py`
- Modify: `backend/app.py`
- Modify: `database/init.sql`
- Modify: `deploy/initdb/01-portal-init.sql`
- Create: `database/migrate_booking_register.sql`
- Create: `tests/test_booking_router.py`
- Create: `portal_ui/src/modules/my/views/BookingRegisterView.vue`
- Create: `portal_ui/src/modules/my/components/BookingFormDialog.vue`
- Create: `portal_ui/src/modules/my/services/api/bookings.ts`
- Create: `portal_ui/src/modules/my/types/bookings.ts`
- Create: `portal_ui/src/modules/my/stores/bookings.ts`
- Create: `portal_ui/tests/unit/booking-register-view.spec.ts`
- Create: `portal_ui/tests/unit/booking-form-dialog.spec.ts`

- [ ] **Step 1: Write the failing booking backend tests**
  - Cover:
    - listing only the current user’s bookings
    - creating a booking without any `resource_pool` coupling
    - cancelling only the current user’s active booking
  - Use a minimal booking model:
    - `id`
    - `user_id`
    - `app_name`
    - `scheduled_for`
    - `purpose`
    - `note`
    - `status`
    - `created_at`
    - `cancelled_at`

- [ ] **Step 2: Run the failing backend tests**
  - Run: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\.venv\Scripts\python.exe -m pytest tests\test_booking_router.py -q`
  - Expected: FAIL because bookings do not exist yet.

- [ ] **Step 3: Implement the minimal booking backend**
  - Add the booking table and migration.
  - Add endpoints:
    - `GET /api/bookings`
    - `POST /api/bookings`
    - `POST /api/bookings/{id}/cancel`
  - Keep the booking service independent from queue/pool/scheduler logic.

- [ ] **Step 4: Write the failing booking frontend tests**
  - Cover:
    - rendering the bookings list
    - creating a booking through `BookingFormDialog`
    - cancelling an active booking

- [ ] **Step 5: Run the failing frontend tests**
  - Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm run test -- booking-register-view.spec.ts booking-form-dialog.spec.ts`
  - Expected: FAIL because the Vue bookings module does not exist.

- [ ] **Step 6: Implement the minimal booking Vue module**
  - Use a small Pinia store around the three booking endpoints.
  - Keep the form intentionally lean: app name,预约时间, purpose, note.
  - Provide list + create + cancel only; no resource dispatch logic.

- [ ] **Step 7: Run the targeted backend and frontend tests to verify they pass**
  - Re-run the commands from Steps 2 and 5.
  - Expected: PASS.

### Final verification

- [ ] **Step 1: Run phase-targeted backend verification**
  - Run: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\.venv\Scripts\python.exe -m pytest tests\test_session_bootstrap.py tests\test_file_move_router.py tests\test_booking_router.py tests\test_task_service_snapshot.py tests\test_worker_repository_pool_disable.py tests\test_resource_pool_service_cancel_pool_tasks.py tests\test_app_attachment_router.py tests\test_admin_pool_attachment_router.py -q`
  - Expected: PASS.

- [ ] **Step 2: Run frontend verification**
  - Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm run test && npm run typecheck && npm run build`
  - Expected: PASS.

- [ ] **Step 3: Run Docker verification**
  - Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation; node --test tests\test_portal_dockerfile_build.mjs`
  - Expected: PASS.

---

## Self-Review

- **Spec coverage:** This plan covers all Phase 5 requirements: Vue workspace migration, file move, Vue tasks, independent booking register, top user area integration, and required tests.
- **Placeholder scan:** No TBD/TODO placeholders remain.
- **Type consistency:** “我的中心” routes consistently use `/my/workspace`, `/my/tasks`, `/my/bookings`; booking stays scheduler-independent; Output links flow back into workspace route query.
- **Assumption made explicit:** `结果中心` remains a topbar external link in this phase, not a routed Vue child view, because the phase goal explicitly closes `个人空间 / App任务 / 预约登记` first.