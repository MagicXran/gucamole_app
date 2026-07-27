# Implementation Plan: RemoteApp 用户文件空间品牌隐藏与会话级友好名称

## Phase 0. Preserve workspace ownership

- [x] Inspect Git status and identify pre-existing user-owned changes.
- [x] Limit this task to new task artifacts and explicitly listed backend/config/test/docs/PoC files.
- [x] Before staging, compare the final changed-file list with the initial status and stage only this task's files.

## Phase 1. TDD for neutral RDP labels

- [x] Add failing `GuacamoleCrypto` tests for explicit/default neutral `client-name` and neutral default `drive-name`.
- [x] Add failing router tests for ASCII normalization, 31-character client-name limit, neutral UNC expansion, old-path compatibility, per-user `drive-path`, and VSCode workspace consistency.
- [x] Add failing config-loader tests for `GUACAMOLE_CLIENT_NAME` and `GUACAMOLE_DRIVE_NAME` overrides.
- [x] Run the focused tests and record the expected failures before production edits.

## Phase 2. Implement neutral connection parameters

- [x] Add shared ASCII RDP label normalization in `backend/router.py`.
- [x] Add `client_name` to `GuacamoleCrypto.build_rdp_connection()` and emit `client-name`.
- [x] Add config/env defaults `Workspace` and `UserFiles`.
- [x] Keep `/drive/portal_u{user_id}`, token usernames, ACLs, and file APIs unchanged.
- [x] Add an idempotent cache/automatic-directory migration.
- [x] Pin matching Guacamole web and guacd images to 1.6.0.
- [x] Run focused tests to green.

## Phase 3. TDD and implementation for the Windows PoC

- [x] Add failing Python-driven PowerShell tests for plan output, exact Chinese shortcut name, session-directory separation, idempotent creation, metadata, invalid identifiers, fixed target, and cleanup.
- [x] Add failing tests for a standalone restricted-profile Known Folder/MountPoints2/Quick Access migration plan.
- [x] Implement `PortalSessionFileSpace.psm1`.
- [x] Implement `set-portal-session-filespace-entry.ps1`.
- [x] Implement `migrate-portal-filespace-labels.ps1` without depending on the user-owned uncommitted restriction modules.
- [x] Run PoC tests against real Windows PowerShell/COM shortcut creation.

## Phase 4. User-facing copy and documentation

- [x] Remove `GuacDrive` from current Portal user-facing help and admin placeholders.
- [x] Update current-state README/runbook/personal-space documentation while preserving historical migration and issue records.
- [x] Append a new `issue_log.md` issue describing the branding leak, neutral transport labels, friendly-entry boundary, cache rollout, and validation requirements.

## Phase 5. Verification

- [x] Focused Python tests: crypto, router, config loader, VSCode policy, PowerShell PoC.
- [x] Full Python suite excluding the documented non-standard `tests/test_file_router.py`.
- [x] Relevant Node/Vitest tests, typecheck, and production build if touched frontend files are in the built Vue path.
- [x] SQL migration static/idempotency checks.
- [x] Docker Compose render and health checks with matching Guacamole 1.6.0 images.
- [x] Inspect the complete task diff and search for missed current user-facing `GuacDrive` strings.
- [x] Attempt real RemoteApp validation; if the Windows host cannot be safely changed, report the exact remaining manual matrix without claiming it passed.

## Phase 6. Review, docs, and commit

- [x] Run Trellis check guidance and independently verify every finding.
- [x] Update the relevant Trellis backend contract for the new RDP-label behavior.
- [x] Preserve CRLF and repository encoding rules.
- [x] Stage only task-owned files and create the required structured commit.
