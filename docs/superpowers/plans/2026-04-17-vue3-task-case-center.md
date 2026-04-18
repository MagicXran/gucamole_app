# Vue3 Task Case Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Do **not** commit during execution because this repo's instructions forbid unrequested commits.

**Goal:** Build a real public task case center where published case packages can be listed, inspected, downloaded, and copied into the current user's workspace without exposing any other user's private task directory.

**Architecture:** Treat `platform_task` and `platform_task_artifact` as the private source of truth, but only expose cases after an explicit publish step builds a sanitized public package. Add a dedicated backend case-center service + router, store public package metadata in new `simulation_case*` tables, and add a Vue `cases` module plus an App-detail “相关案例” entry that only reads published cases.

**Tech Stack:** Vue 3, Vue Router, Pinia, Axios, Vitest, FastAPI, pytest, MySQL 8, zipfile/pathlib.

---

### Task 1: Add case-center schema and publish-package backend core

**Files:**
- Create: `backend/case_center_service.py`
- Create: `backend/case_center_router.py`
- Modify: `backend/models.py`
- Modify: `backend/app.py`
- Modify: `database/init.sql`
- Modify: `deploy/initdb/01-portal-init.sql`
- Create: `database/migrate_simulation_case_center.sql`
- Create: `tests/test_case_center_service.py`

- [ ] **Step 1: Write the failing publish-package tests**
  - Cover:
    - explicit publish from a succeeded task copies only public package content
    - publish reads from task output/private artifacts but produces a separate package root
    - publish does **not** automatically expose raw task workspace paths
    - publish stores rows across:
      - `simulation_case`
      - `simulation_case_source`
      - `simulation_case_asset`
      - `simulation_case_package`

- [ ] **Step 2: Run the backend tests to verify they fail**
  - Run: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\.venv\Scripts\python.exe -m pytest tests\test_case_center_service.py -q`
  - Expected: FAIL because case-center service/schema do not exist yet.

- [ ] **Step 3: Implement the minimal publish backend**
  - Add schema for:
    - `simulation_case`
    - `simulation_case_source`
    - `simulation_case_asset`
    - `simulation_case_package`
  - Add service methods for:
    - creating a published case from a succeeded task
    - sanitizing and copying package contents into a public package root
    - building a zip archive for download
  - Keep package files outside any user private root path.

- [ ] **Step 4: Run the backend tests to verify they pass**
  - Re-run: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\.venv\Scripts\python.exe -m pytest tests\test_case_center_service.py -q`
  - Expected: PASS.

### Task 2: Expose case list/detail/download/transfer APIs

**Files:**
- Modify: `backend/case_center_service.py`
- Modify: `backend/case_center_router.py`
- Modify: `backend/file_router.py` (only if a tiny shared helper is needed; otherwise leave untouched)
- Create: `tests/test_case_center_router.py`

- [ ] **Step 1: Write the failing router tests**
  - Cover:
    - `GET /api/cases` returns only published cases
    - `GET /api/cases/{case_id}` returns public package metadata, not private task paths
    - `GET /api/cases/{case_id}/download` serves the package archive
    - `POST /api/cases/{case_id}/transfer` copies package contents into the current user's workspace
    - transfer/download never read another user's private task directory directly

- [ ] **Step 2: Run the backend tests to verify they fail**
  - Run: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\.venv\Scripts\python.exe -m pytest tests\test_case_center_router.py -q`
  - Expected: FAIL because the public APIs do not exist yet.

- [ ] **Step 3: Implement the minimal public APIs**
  - Add endpoints:
    - `GET /api/cases`
    - `GET /api/cases/{case_id}`
    - `GET /api/cases/{case_id}/download`
    - `POST /api/cases/{case_id}/transfer`
  - Optional query params for list:
    - `keyword`
    - `app_id`
  - Transfer target defaults to a safe workspace path such as `Cases/<case-slug>/`.

- [ ] **Step 4: Run the backend tests to verify they pass**
  - Re-run: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\.venv\Scripts\python.exe -m pytest tests\test_case_center_router.py -q`
  - Expected: PASS.

### Task 3: Add Vue case list/detail pages and navigation entry

**Files:**
- Modify: `backend/identity_access.py`
- Modify: `tests/test_session_bootstrap.py`
- Modify: `portal_ui/src/router/index.ts`
- Create: `portal_ui/src/modules/cases/views/CaseListView.vue`
- Create: `portal_ui/src/modules/cases/views/CaseDetailView.vue`
- Create: `portal_ui/src/modules/cases/services/api/cases.ts`
- Create: `portal_ui/src/modules/cases/types/cases.ts`
- Create: `portal_ui/src/modules/cases/stores/cases.ts`
- Create: `portal_ui/src/modules/cases/routes.ts`
- Create: `portal_ui/tests/unit/case-list-view.spec.ts`
- Create: `portal_ui/tests/unit/case-detail-view.spec.ts`

- [ ] **Step 1: Write the failing Vue/tests and session menu tests**
  - Cover:
    - bootstrap menu tree includes a visible case-center entry while keeping compute as default landing
    - `/cases` renders published cases
    - keyword filtering works
    - `/cases/:caseId` renders package detail and actions

- [ ] **Step 2: Run the tests to verify they fail**
  - Run: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\.venv\Scripts\python.exe -m pytest tests\test_session_bootstrap.py -q`
  - Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm run test -- case-list-view.spec.ts case-detail-view.spec.ts`
  - Expected: FAIL because the case-center route/menu/pages do not exist.

- [ ] **Step 3: Implement the minimal Vue case center**
  - Add a top-level `任务案例` navigation entry (without changing compute as default).
  - Add case list/detail routes.
  - Build a small Pinia store for list/detail/filter state.
  - Wire list/detail pages to the new public APIs.

- [ ] **Step 4: Run the tests to verify they pass**
  - Re-run the commands from Step 2.
  - Expected: PASS.

### Task 4: Link App detail to related published cases

**Files:**
- Modify: `portal_ui/src/modules/compute/views/AppDetailView.vue`
- Modify: `portal_ui/src/services/api/compute.ts` or add a small shared case API import if cleaner
- Modify: `portal_ui/tests/unit/app-detail-view.spec.ts`

- [ ] **Step 1: Write the failing App-detail related-cases test**
  - Cover:
    - App detail page shows a “相关案例” section or entry
    - related cases are filtered by the current app/runtime identity
    - clicking the entry lands in the case center or case detail

- [ ] **Step 2: Run the targeted test to verify it fails**
  - Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm run test -- app-detail-view.spec.ts`
  - Expected: FAIL because App detail has no case-center linkage yet.

- [ ] **Step 3: Implement the minimal linkage**
  - Show a related-case entry in App detail using published case data only.
  - Do not expose unpublished candidates or private task information.

- [ ] **Step 4: Run the targeted test to verify it passes**
  - Re-run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm run test -- app-detail-view.spec.ts`
  - Expected: PASS.

### Final verification

- [ ] **Step 1: Run Phase 6 backend verification**
  - Run: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\.venv\Scripts\python.exe -m pytest tests\test_case_center_service.py tests\test_case_center_router.py tests\test_session_bootstrap.py -q`
  - Expected: PASS.

- [ ] **Step 2: Run Docker verification**
  - Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation; node --test tests\test_portal_dockerfile_build.mjs`
  - Expected: PASS.

- [ ] **Step 3: Run frontend verification**
  - Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm run test && npm run typecheck && npm run build`
  - Expected: PASS.

---

## Self-Review

- **Spec coverage:** This plan covers explicit publish-package logic, public case list/detail/download/transfer APIs, Vue case list/detail pages, and App-detail related-case linkage.
- **Placeholder scan:** No TBD/TODO placeholders remain.
- **Type consistency:** Public case consumption always reads from published package metadata; download/transfer never target raw private task roots.
- **Scope choice:** Publish is explicit, not automatic. This satisfies “成功任务 ≠ 自动公开案例” while still making “成功任务 -> 候选/发布包” operational.