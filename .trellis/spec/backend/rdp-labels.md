# RDP Label Contract

## Scenario: Stable user-space labels for all RemoteApp connections

### 1. Runtime Values

```text
client-name: Workspace
drive-name: 用户空间
drive-path: /drive/portal_u{user_id}
automatic remote-app-dir: \\tsclient\用户空间
native Windows label: Workspace 上的 用户空间
```

### 2. Contracts

- `client-name` must be short ASCII. The fixed value is `Workspace`; empty values and the legacy Chinese value `用户空间` normalize to `Workspace` before JSON Auth generation.
- `drive-name` remains the fixed Chinese label `用户空间` and requires the pinned `nercar-portal-guacd:1.6.0-user-space` byte-length patch.
- The label is not an authorization boundary. Per-user storage isolation remains `/drive/portal_u{user_id}`.
- New applications inherit these global values. Application-specific launchers may replace the native file dialog, but must not change the per-user drive path.
- Changing either label requires recreating `portal-backend`, clearing `token_cache`, ending old Windows sessions, and validating a newly generated JSON Auth payload.
- When reverting to the official unpatched guacd image, restore `drive-name=UserFiles` and `\\tsclient\UserFiles`; `client-name=Workspace` remains valid.

### 3. Required Tests

- Config and environment defaults produce `Workspace` plus `用户空间`.
- Router normalization converts empty, unsafe Unicode, and legacy Chinese client names to `Workspace` while preserving valid ASCII overrides and the 31-character limit.
- JSON Auth connection defaults contain the ASCII client name, Chinese drive name, and per-user drive path.
- Compose and environment examples use the same defaults.
- A real new Windows session shows `Workspace 上的 用户空间`, can browse `\\tsclient\用户空间`, and does not expose another Portal user's directory.
