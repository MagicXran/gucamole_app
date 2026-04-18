# Vue3 SDK Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Do **not** commit during execution because this repo's instructions forbid unrequested commits.

**Goal:** Build the `云平台SDK / 仿真AppSDK` center as versioned SDK packages with release notes and downloadable assets, not a generic file list.

**Architecture:** Add a dedicated SDK backend boundary with `sdk_package`, `sdk_version`, and `sdk_asset` tables, exposing read-only package/version/asset query and download APIs. Add a Vue `sdk` module with two pages filtered by SDK category, sharing one store/service layer while keeping package versions explicit in the UI.

**Tech Stack:** Vue 3, Vue Router, Pinia, Axios, Vitest, FastAPI, pytest, MySQL 8.

---

### Task 1: Add SDK schema and public read APIs

**Files:**
- Create: `backend/sdk_center_service.py`
- Create: `backend/sdk_center_router.py`
- Modify: `backend/models.py`
- Modify: `backend/app.py`
- Modify: `database/init.sql`
- Modify: `deploy/initdb/01-portal-init.sql`
- Create: `database/migrate_sdk_center.sql`
- Create: `tests/test_sdk_center_router.py`

- [ ] **Step 1: Write the failing backend tests**
  - Cover:
    - `GET /api/sdks?package_kind=cloud_platform` returns only active cloud-platform SDK packages.
    - `GET /api/sdks?package_kind=simulation_app` returns only active simulation-app SDK packages.
    - `GET /api/sdks/{package_id}` returns package detail with versions and assets.
    - `GET /api/sdks/assets/{asset_id}/download` redirects or serves only active downloadable assets.
    - inactive packages / inactive versions / inactive assets are hidden.

- [ ] **Step 2: Run backend tests to verify they fail**
  - Run: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\.venv\Scripts\python.exe -m pytest tests\test_sdk_center_router.py -q`
  - Expected: FAIL because SDK router/service/schema do not exist.

- [ ] **Step 3: Implement the minimal SDK backend**
  - Add tables:
    - `sdk_package`
    - `sdk_version`
    - `sdk_asset`
  - Use explicit fields:
    - package: `package_key`, `package_kind`, `name`, `summary`, `is_active`
    - version: `version`, `release_notes`, `release_date`, `is_latest`, `is_active`
    - asset: `asset_kind`, `file_name`, `download_url`, `size_bytes`, `checksum`, `is_active`
  - Add read APIs:
    - `GET /api/sdks`
    - `GET /api/sdks/{package_id}`
    - `GET /api/sdks/assets/{asset_id}/download`
  - Keep download assets URL-based for now; do not pretend this is personal-space file browsing.

- [ ] **Step 4: Run backend tests to verify they pass**
  - Re-run: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\.venv\Scripts\python.exe -m pytest tests\test_sdk_center_router.py -q`
  - Expected: PASS.

### Task 2: Add Vue SDK center routes, navigation, and shared module

**Files:**
- Modify: `backend/identity_access.py`
- Modify: `tests/test_session_bootstrap.py`
- Modify: `portal_ui/src/router/index.ts`
- Modify: `portal_ui/src/stores/navigation.ts`
- Create: `portal_ui/src/modules/sdk/views/CloudSdkView.vue`
- Create: `portal_ui/src/modules/sdk/views/SimulationAppSdkView.vue`
- Create: `portal_ui/src/modules/sdk/components/SdkPackageList.vue`
- Create: `portal_ui/src/modules/sdk/components/SdkVersionPanel.vue`
- Create: `portal_ui/src/modules/sdk/services/api/sdk.ts`
- Create: `portal_ui/src/modules/sdk/types/sdk.ts`
- Create: `portal_ui/src/modules/sdk/stores/sdk.ts`
- Create: `portal_ui/src/modules/sdk/routes.ts`
- Create: `portal_ui/tests/unit/sdk-center-view.spec.ts`

- [ ] **Step 1: Write the failing frontend/menu tests**
  - Cover:
    - session menu includes `SDK中心` with children `/sdk/cloud` and `/sdk/simulation-app` while compute remains first.
    - `/sdk/cloud` renders only cloud-platform packages.
    - `/sdk/simulation-app` renders only simulation-app packages.
    - search filters by package name/summary.
    - version list and release notes are visible.
    - download link/action points to `/api/sdks/assets/{asset_id}/download`.

- [ ] **Step 2: Run tests to verify they fail**
  - Run: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\.venv\Scripts\python.exe -m pytest tests\test_session_bootstrap.py -q`
  - Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm run test -- sdk-center-view.spec.ts`
  - Expected: FAIL because SDK routes/menu/pages do not exist.

- [ ] **Step 3: Implement the minimal Vue SDK center**
  - Add `SDK中心` menu group after `任务案例`.
  - Add routes:
    - `/sdk/cloud`
    - `/sdk/simulation-app`
  - Build shared store around SDK APIs.
  - Build list/version UI that makes versions first-class, not hidden.

- [ ] **Step 4: Run tests to verify they pass**
  - Re-run the commands from Step 2.
  - Expected: PASS.

### Task 3: Final verification and review

**Files:**
- No new files expected beyond Tasks 1-2.

- [ ] **Step 1: Run Phase 7 backend verification**
  - Run: `D:\Nercar\NanGang\PSD\Apps\gucamole_app\.venv\Scripts\python.exe -m pytest tests\test_sdk_center_router.py tests\test_session_bootstrap.py -q`
  - Expected: PASS.

- [ ] **Step 2: Run Docker verification**
  - Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation; node --test tests\test_portal_dockerfile_build.mjs`
  - Expected: PASS.

- [ ] **Step 3: Run frontend verification**
  - Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm run test && npm run typecheck && npm run build`
  - Expected: PASS.

---

## Self-Review

- **Spec coverage:** This plan covers `sdk_package / sdk_version / sdk_asset`, cloud SDK and simulation App SDK pages, search, versions, release notes, and downloads.
- **Placeholder scan:** No TBD/TODO placeholders remain.
- **Type consistency:** Backend and frontend consistently use `package_kind = cloud_platform | simulation_app`, and every SDK package has explicit versions.
- **Scope choice:** This phase is read-only SDK publishing/consumption. Admin SDK management is intentionally not included; do not bloat the phase.