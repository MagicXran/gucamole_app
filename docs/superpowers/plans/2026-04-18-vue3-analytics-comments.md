# Vue3 Analytics Dashboard and Comments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Do **not** commit during execution because this repo's instructions forbid unrequested commits.

**Goal:** Finish Phase 9 by adding a minimal operations-grade analytics dashboard and comment loop, without dragging in a fake BI framework or a bloated social system.

**Architecture:** Reuse existing business tables first: software access comes from `audit_log` launch records, project access comes from case access/download/transfer audit records, and personnel aggregation joins `portal_user` on those same events. Add a small admin analytics API plus a Vue analytics view under the admin workbench, and add a dedicated comment boundary that hangs only off App detail and Case detail instead of becoming a new global center.

**Tech Stack:** Vue 3, Vue Router, Pinia, Axios, Vitest, FastAPI, pytest, MySQL 8.

---

### Task 1: Add analytics events and admin analytics backend

**Files:**
- Create: `backend/admin_analytics_router.py`
- Create: `backend/admin_analytics_service.py`
- Modify: `backend/app.py`
- Modify: `backend/models.py`
- Modify: `backend/identity_access.py`
- Modify: `backend/case_center_router.py`
- Modify: `backend/app_attachment_router.py` or add a tiny analytics hook at the actual app-detail read boundary if cleaner
- Modify: `database/init.sql`
- Modify: `deploy/initdb/01-portal-init.sql`
- Create: `database/migrate_admin_analytics.sql`
- Create: `tests/test_admin_analytics_router.py`
- Modify: `tests/test_session_bootstrap.py`

- [ ] **Step 1: Write the failing backend analytics tests**
  - Cover:
    - `GET /api/admin/analytics/overview` returns:
      - software access ranking from `audit_log(action='launch_app')`
      - project/case access ranking from case detail/download/transfer events
      - user ranking and department grouping
    - department aggregation tolerates empty department and groups it as `未设置`
    - analytics route requires admin
    - session bootstrap adds `统计看板` under the admin menu only for admins

- [ ] **Step 2: Run the failing backend tests**
  - Run: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\.venv\Scripts\python.exe -m pytest tests\test_admin_analytics_router.py tests\test_session_bootstrap.py -q`
  - Expected: FAIL because analytics backend and menu entry do not exist yet.

- [ ] **Step 3: Implement the minimal analytics backend**
  - Add a single admin analytics endpoint: `GET /api/admin/analytics/overview`.
  - Reuse existing `audit_log`, `remote_app`, `simulation_case`, `portal_user`.
  - Add the minimal schema support needed for department grouping (`portal_user.department` if absent).
  - Log case detail/download/transfer access and app-detail attachment reads as analytics events so the dashboard is fed by real usage, not static counts.
  - Keep output narrow: overview cards + top software + top projects + user/department slices.

- [ ] **Step 4: Run the backend tests to verify they pass**
  - Re-run: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\.venv\Scripts\python.exe -m pytest tests\test_admin_analytics_router.py tests\test_session_bootstrap.py -q`
  - Expected: PASS.

### Task 2: Add the Vue analytics dashboard inside the admin workbench

**Files:**
- Create: `portal_ui/src/modules/admin/types/analytics.ts`
- Create: `portal_ui/src/modules/admin/services/api/analytics.ts`
- Create: `portal_ui/src/modules/admin/stores/analytics.ts`
- Create: `portal_ui/src/modules/admin/views/AdminAnalyticsView.vue`
- Modify: `portal_ui/src/modules/admin/routes.ts`
- Modify: `portal_ui/src/modules/admin/views/AdminDashboardView.vue`
- Modify: `portal_ui/src/stores/navigation.ts`
- Create: `portal_ui/tests/unit/admin-analytics-view.spec.ts`
- Modify: `portal_ui/tests/unit/admin-navigation.spec.ts`

- [ ] **Step 1: Write the failing Vue analytics tests**
  - Cover:
    - admin menu includes `统计看板`
    - `/admin/analytics` route renders the analytics dashboard
    - dashboard shows software ranking, project ranking, user ranking, department grouping
    - non-admin direct route is still redirected away

- [ ] **Step 2: Run the failing Vue analytics tests**
  - Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm run test -- admin-navigation.spec.ts admin-analytics-view.spec.ts`
  - Expected: FAIL because analytics route/view/store do not exist yet.

- [ ] **Step 3: Implement the minimal Vue analytics dashboard**
  - Add `统计看板` under the existing admin workbench, not a new top-level menu.
  - Render plain, truthful blocks and tables; no charting library unless existing tooling truly demands it.
  - Keep the dashboard lightweight and operations-facing.

- [ ] **Step 4: Run the Vue analytics tests to verify they pass**
  - Re-run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm run test -- admin-navigation.spec.ts admin-analytics-view.spec.ts`
  - Expected: PASS.

### Task 3: Add comments backend and hang comments off App/Case detail

**Files:**
- Create: `backend/comment_router.py`
- Create: `backend/comment_service.py`
- Modify: `backend/app.py`
- Modify: `backend/models.py`
- Modify: `database/init.sql`
- Modify: `deploy/initdb/01-portal-init.sql`
- Create: `database/migrate_portal_comment.sql`
- Create: `tests/test_comment_router.py`
- Create: `portal_ui/src/services/api/comments.ts`
- Create: `portal_ui/src/types/comments.ts`
- Create: `portal_ui/src/components/comments/CommentThread.vue`
- Create: `portal_ui/tests/unit/comment-thread.spec.ts`
- Modify: `portal_ui/src/modules/compute/views/AppDetailView.vue`
- Modify: `portal_ui/src/modules/cases/views/CaseDetailView.vue`
- Modify: `portal_ui/tests/unit/app-detail-view.spec.ts`
- Modify: `portal_ui/tests/unit/case-detail-view.spec.ts`

- [ ] **Step 1: Write the failing backend comment tests**
  - Cover:
    - list comments for App detail
    - create comment for App detail
    - list comments for Case detail
    - create comment for Case detail
    - invalid target or unpublished case is rejected
    - unauthenticated comment creation is blocked

- [ ] **Step 2: Run the failing backend comment tests**
  - Run: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\.venv\Scripts\python.exe -m pytest tests\test_comment_router.py -q`
  - Expected: FAIL because comments backend does not exist.

- [ ] **Step 3: Write the failing Vue comment tests**
  - Cover:
    - `CommentThread` renders existing comments
    - authenticated user can submit a new comment
    - App detail shows the comment thread
    - Case detail shows the comment thread
    - comments do not create a new top-level route/menu

- [ ] **Step 4: Run the failing Vue comment tests**
  - Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm run test -- comment-thread.spec.ts app-detail-view.spec.ts case-detail-view.spec.ts`
  - Expected: FAIL because comments UI does not exist.

- [ ] **Step 5: Implement the minimal comments loop**
  - Add one compact `portal_comment` table with:
    - `target_type` (`app` / `case`)
    - `target_id`
    - `user_id`
    - `content`
    - timestamps
  - Add list/create APIs.
  - Mount one shared `CommentThread` component inside App detail and Case detail.
  - Do not add comment editing, likes, nesting, or a top-level comment center.

- [ ] **Step 6: Run the targeted backend and Vue tests to verify they pass**
  - Re-run:
    - `D:\Nercar\NanGang\PSD\Apps\gucamole_app\.venv\Scripts\python.exe -m pytest tests\test_comment_router.py -q`
    - `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm run test -- comment-thread.spec.ts app-detail-view.spec.ts case-detail-view.spec.ts`
  - Expected: PASS.

### Task 4: Run Phase 9 verification and final review

**Files:**
- Modify: Phase 9 files above only as required by verification/review feedback

- [ ] **Step 1: Run phase-targeted backend verification**
  - Run: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\.venv\Scripts\python.exe -m pytest tests\test_admin_analytics_router.py tests\test_comment_router.py tests\test_session_bootstrap.py tests\test_admin_pool_router.py tests\test_admin_worker_router.py tests\test_monitor_reclaim.py -q`
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
  - Expected: existing `tests\test_file_router.py` failure remains known and non-Phase-9, unless new Phase 9 regressions appear elsewhere.

- [ ] **Step 5: Request final code review**
  - Run a final scoped spec review and code-quality review for Phase 9 only.
  - If either reviewer finds `Critical` / `Important`, fix them before calling Phase 9 complete.

---

## Self-Review

- **Spec coverage:** This plan covers the two explicit Phase 9 deliverables: analytics dashboard and comments, with comments hanging only off App/Case detail.
- **Placeholder scan:** No TBD/TODO placeholders remain.
- **Type consistency:** Analytics stays under the admin workbench; comments stay in detail pages; no top-level comment center is introduced.
- **Scope choice:** This phase deliberately avoids a charting framework, threaded discussions, likes, or a separate BI subsystem. Minimal closed loop only.
