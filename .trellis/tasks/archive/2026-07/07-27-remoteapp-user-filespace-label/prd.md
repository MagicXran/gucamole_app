# RemoteApp 用户文件空间品牌隐藏与会话级友好名称

## Goal

消除 RemoteApp 文件选择器中的 Guacamole/GuacDrive 技术标识，并为会话级用户文件空间入口建立可验证实现。

## Requirements

### R1. Remove product-facing Guacamole identifiers

- Every generated RDP connection must explicitly provide a neutral ASCII `client-name`.
- The redirected filesystem must use a neutral ASCII `drive-name`.
- Defaults and user-facing Portal copy must not expose `Guacamole RDP` or `GuacDrive`.
- `client-name` is limited to a safe ASCII value of at most 31 bytes; `drive-name` keeps the repository's existing 64-character ASCII compatibility policy.

### R2. Preserve storage, security, and session contracts

- Keep the physical path `/drive/portal_u{user_id}` unchanged.
- Keep Guacamole token cache keys as `portal_u{user_id}` and preserve per-user multi-tab token reuse.
- Keep `remote_app_dir` and VSCode workspace expansion consistent with the effective neutral `drive-name`.
- Treat historical `\\tsclient\GuacDrive` and `\\tsclient\用户数据目录` values as automatic compatibility paths, not explicit application-owned directories.

### R3. Invalidate stale connection payloads

- Provide an idempotent migration that clears persisted token cache entries containing old connection parameters.
- Deployment instructions must require a backend restart and termination of old Windows sessions because the cache also exists in memory and established RDP sessions cannot be renamed in place.

### R4. Provide a session-scoped friendly-entry proof of concept

- Add an independent Windows PowerShell module and command that create a session-specific shortcut named `{display_name or username}的文件空间`.
- Add a standalone administrator migration that updates restricted-account Known Folders from historical UNC values to `\\tsclient\UserFiles` and removes stale MountPoints2/Quick Access state.
- The shortcut target remains the neutral internal UNC `\\tsclient\UserFiles`.
- Entry directories are keyed by Windows Session ID and Portal Session UUID to avoid concurrent shared-account sessions overwriting the same file.
- The command must support idempotent create/update and cleanup, validate names and identifiers, and emit machine-readable JSON.
- This proof of concept is a presentation-layer entry only. It must not be documented as Windows hard isolation or as the final generic application Launcher.

### R5. Keep scope narrow and compatible

- Do not change ACL, security-mode, resource-pool, file API, quota, Nginx download, AppLocker, GPO, Firewall, or physical storage semantics.
- Do not implement the separate generic application runtime-profile/Launcher task in this change.
- Keep historical migration and issue records intact; append new current-state documentation instead of rewriting prior failures.

## Acceptance Criteria

- [x] Generated RDP parameters contain neutral ASCII `client-name=Workspace` and `drive-name=UserFiles` and contain neither `Guacamole RDP` nor `GuacDrive`.
- [x] `drive-path` remains `/drive/portal_u{user_id}` for different Portal users.
- [x] Default RemoteApp working directories and restricted VSCode workspace arguments use `\\tsclient\UserFiles`.
- [x] Old automatic UNC values are normalized to the current neutral UNC while explicitly configured application directories remain unchanged.
- [x] Configuration environment overrides for both neutral names are covered by tests and still pass through the same sanitization boundary.
- [x] A new migration clears `token_cache` without changing user, ACL, application, or file-space records.
- [x] The Windows PoC creates, updates, describes, and removes a session-specific `{用户名}的文件空间.lnk` without writing to shared Desktop or HKCU locations.
- [x] The Windows administrator migration reports affected profiles, updates only historical automatic paths, removes legacy shell cache, and marks active accounts as requiring logoff.
- [x] Concurrent PoC plans for two Windows/Portal session pairs produce different entry directories and do not overwrite one another.
- [x] Backend unit tests, relevant frontend tests/build checks, PowerShell PoC tests, and repository diff checks pass.
- [x] README and `issue_log.md` describe the neutral transport names, friendly-entry boundary, rollout, rollback, and remaining real-Windows validation honestly.

## Notes

- Keep `prd.md` focused on requirements, constraints, and acceptance criteria.
- Lightweight tasks can remain PRD-only.
- For complex tasks, add `design.md` for technical design and `implement.md` for execution planning before `task.py start`.
