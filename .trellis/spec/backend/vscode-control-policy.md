# VSCode Control Policy Contract

## Scenario: Restricted VSCode and RemoteApp security modes

### 1. Scope / Trigger

- Trigger: any change to `remote_app.security_mode`, `vscode_control_profile`, RemoteApp launch arguments, Guacamole channel permissions, or ordinary-user ACL behavior.
- The contract spans MySQL, Pydantic models, Admin APIs, launch-time connection generation, session-cache invalidation, and Windows policy handoff.

### 2. Signatures

- Database:
  - `remote_app.security_mode`: `restricted_remoteapp | restricted_vscode | admin_desktop`
  - `remote_app.vscode_control_profile_id`: nullable FK to `vscode_control_profile.id`
  - `vscode_control_profile`: versioned permissions, allowlists, fixed roots, revision, active state.
- Admin APIs:
  - `GET /api/admin/vscode-control-catalog`
  - `GET|POST /api/admin/vscode-control-profiles`
  - `PUT|DELETE /api/admin/vscode-control-profiles/{id}`
  - `GET /api/admin/vscode-control-profiles/{id}/effective`
- Launch boundary:
  - `_build_all_connections_with_errors(user_id) -> (connections, errors)`
  - `build_vscode_arguments(profile, user_id, drive_name=...) -> str`

### 3. Contracts

- `backend/vscode_policy_service.py` is the only backend owner of control codes, defaults, allowlist dependencies, locked baselines, and effective Guacamole mapping.
- All current grantable controls default to `true` for a new profile.
- `C:\PortalProfiles`, `C:\PortalExtensions`, and the `\\tsclient\{user_drive}` template are fixed values; `{user_drive}` is expanded from the current Portal user's display name at launch.
- Executable allowlists contain local absolute Windows executable/script paths; extension entries use `publisher.extension`; network entries use host, host:port, CIDR, or HTTP(S) URL.
- App/ACL/profile mutations must invalidate all Guacamole sessions.
- Per-user token reuse remains unchanged: all valid user connections are packaged into one token.

### 4. Validation & Error Matrix

- restricted mode + empty `remote_app` -> Admin API `400`; launch skips the invalid connection and target launch returns `409`.
- `restricted_vscode` + missing/inactive/invalid profile -> `400` on save/bind; `409` on launch if stale DB state remains.
- ordinary user + `admin_desktop` ACL -> `400`; list/launch SQL also filters it.
- unknown or missing control code -> `400`.
- enabled dependent control + empty required allowlist -> profile `valid=false`; active save/bind is rejected.
- wildcard, UNC executable path, arbitrary profile root, invalid extension ID, or invalid network target -> `400`.
- malformed profile data read from DB -> normalized to `VscodePolicyError`; other valid connections remain available.

### 5. Good / Base / Bad Cases

- Good: active profile has all required allowlists; user 11 gets `C:\PortalProfiles\11` and `C:\PortalExtensions\11`.
- Base: inactive default profile keeps every permission selected but remains invalid until allowlists are populated.
- Bad: storing `C:\Windows` as a profile root or `*` as an allowlist entry.

### 6. Tests Required

- Assert the catalog contains every control exactly once and defaults all to `true`.
- Assert fixed roots, wildcard, unknown controls, invalid extension/network/executable formats are rejected.
- Assert users A/B receive different VSCode arguments and no literal `{user_id}` remains.
- Assert restricted RemoteApp channels are forced strict.
- Assert ordinary-user ACL cannot include `admin_desktop`.
- Assert schema migration is idempotent and the schema verifier sees the new table/columns.
- Run live API smoke against Docker/MySQL after migration.

### 7. Wrong vs Correct

#### Wrong

```python
remote_app_args = app["remote_app_args"].format(user_id=user_id)
```

This trusts arbitrary templates, allows unknown placeholders, and can break multi-user profile isolation.

#### Correct

```python
profile = profile_from_row(app, prefix="vcp_")
remote_app_args = build_vscode_arguments(profile, user_id, drive_name=drive_name)
```

The service owns fixed roots, validation, effective permissions, and the only allowed argument shape.
