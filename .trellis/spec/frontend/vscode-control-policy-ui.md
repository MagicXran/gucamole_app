# VSCode Control Policy UI Contract

## Scenario: Admin policy editor and application binding

### 1. Scope / Trigger

- Trigger: changes to the VSCode policy page, control matrix, allowlist editors, security-mode selection, or profile binding in the Admin application dialog.

### 2. Signatures

- Route: `/admin/vscode-policies`, `meta.requiresAdmin=true`.
- Menu path is supplied by backend session bootstrap as `/admin/vscode-policies`.
- UI modules:
  - `types/vscodePolicies.ts`
  - `services/api/vscodePolicies.ts`
  - `stores/vscodePolicies.ts`
  - `views/AdminVscodePoliciesView.vue`
  - policy dialog, permission matrix, and allowlist editor components.

### 3. Contracts

- Render controls from the backend catalog; never maintain a second hard-coded control list.
- New profiles clone `catalog.default_permissions`, so all current controls start selected.
- Provide Select All, Clear All, and Reset Defaults.
- Show locked baseline items as checked and disabled.
- Fixed roots and the `\\tsclient\用户数据目录` workspace are visible but disabled.
- The application dialog only selects `security_mode` and a ready profile; it does not embed the policy matrix.

### 4. Validation & Error Matrix

- enabled profile + missing required allowlist -> show warning and block submit.
- inactive or invalid profile option -> disabled; stale selected invalid profile -> block submit before API call.
- restricted mode + empty RemoteApp -> block submit.
- `restricted_vscode` + no ready profile -> block submit.
- backend `400/409` -> store keeps the dialog open and exposes the request error.

### 5. Good / Base / Bad Cases

- Good: admin fills all required allowlists, enables the profile, then binds it to a VSCode application.
- Base: admin saves an inactive invalid draft with all controls selected.
- Bad: UI enables an invalid profile option and relies only on backend rejection.

### 6. Tests Required

- Assert default checkboxes, Select All, Clear All, and Reset Defaults.
- Assert missing allowlist warning and active-submit blocking.
- Assert invalid/inactive profile options are disabled and not submitted.
- Assert application payload includes `security_mode` and `vscode_control_profile_id`.
- Assert route, menu, breadcrumb, typecheck, full Vitest suite, and production build.

### 7. Wrong vs Correct

#### Wrong

```ts
const controls = ['terminal', 'tasks', 'debug']
```

This drifts from backend policy versions and silently omits new controls.

#### Correct

```ts
form.permissions = { ...catalog.default_permissions }
```

The backend catalog remains the single source of truth for codes, defaults, risks, and allowlist dependencies.
