# Vue3 Portal Shell Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first production-safe Vue3 portal foundation without breaking the current plain-JS portal, including the new shell, session bootstrap, and the default `计算资源 / 商业软件` flow.

**Architecture:** Add a new `portal_ui` Vue3 application under `/portal/` while keeping the existing `frontend/` pages alive as fallback. The backend exposes a new session bootstrap API and keeps all current runtime APIs stable so the Vue shell can progressively consume them. Authentication must support local mode today and upstream-token mode later behind one unified bootstrap contract.

**Tech Stack:** Vue 3, Vite, Vue Router, Pinia, Axios, Element Plus, Vitest, FastAPI, pytest.

---

### Task 1: Scaffold the Vue3 shell workspace

**Files:**
- Create: `portal_ui/package.json`
- Create: `portal_ui/vite.config.ts`
- Create: `portal_ui/tsconfig.json`
- Create: `portal_ui/tsconfig.node.json`
- Create: `portal_ui/index.html`
- Create: `portal_ui/src/main.ts`
- Create: `portal_ui/src/App.vue`
- Create: `portal_ui/src/styles/index.scss`
- Create: `portal_ui/tests/unit/app-shell.spec.ts`
- Modify: `package.json`

- [ ] **Step 1: Write the failing shell smoke test**

```ts
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import App from '../../src/App.vue'

describe('App shell bootstrap', () => {
  it('renders router host container', () => {
    const wrapper = mount(App, {
      global: {
        stubs: {
          RouterView: { template: '<div data-testid="router-view" />' },
        },
      },
    })

    expect(wrapper.find('[data-testid="router-view"]').exists()).toBe(true)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm run test -- app-shell.spec.ts`
Expected: FAIL because `portal_ui` and `src/App.vue` do not exist yet

- [ ] **Step 3: Write minimal Vue workspace files**

```json
{
  "name": "portal-ui",
  "private": true,
  "version": "0.0.1",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "test": "vitest run"
  },
  "dependencies": {
    "axios": "^1.9.0",
    "element-plus": "^2.9.8",
    "pinia": "^3.0.2",
    "vue": "^3.5.13",
    "vue-router": "^4.5.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.2.1",
    "@vue/test-utils": "^2.4.6",
    "jsdom": "^26.0.0",
    "sass": "^1.86.3",
    "typescript": "^5.8.3",
    "vite": "^6.3.2",
    "vitest": "^3.1.3"
  }
}
```

```ts
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  base: '/portal/',
  plugins: [vue()],
  build: {
    outDir: '../frontend/portal',
    emptyOutDir: true,
  },
  test: {
    environment: 'jsdom',
  },
})
```

```ts
import { createApp } from 'vue'
import App from './App.vue'
import './styles/index.scss'

createApp(App).mount('#app')
```

```vue
<template>
  <RouterView />
</template>

<script setup lang="ts">
import { RouterView } from 'vue-router'
</script>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm install && npm run test -- app-shell.spec.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add package.json portal_ui/package.json portal_ui/vite.config.ts portal_ui/tsconfig.json portal_ui/tsconfig.node.json portal_ui/index.html portal_ui/src/main.ts portal_ui/src/App.vue portal_ui/src/styles/index.scss portal_ui/tests/unit/app-shell.spec.ts
git commit -m "feat: scaffold vue3 portal workspace"
```

### Task 2: Add session bootstrap and auth adapter foundation

**Files:**
- Create: `backend/session_router.py`
- Create: `backend/identity_access.py`
- Create: `tests/test_session_bootstrap.py`
- Modify: `backend/app.py`

- [ ] **Step 1: Write the failing bootstrap test**

```python
from fastapi.testclient import TestClient

from backend.app import app


def test_session_bootstrap_returns_local_user_context(monkeypatch):
    from backend import session_router

    monkeypatch.setattr(
        session_router,
        "resolve_session_context",
        lambda request: {
            "user": {
                "user_id": 2,
                "username": "test",
                "display_name": "测试用户",
                "is_admin": False,
            },
            "auth_source": "local",
            "capabilities": ["compute.view", "workspace.view", "task.view"],
            "menu_tree": [{"key": "compute", "title": "计算资源"}],
            "org_context": {"department": ""},
        },
    )

    client = TestClient(app)
    response = client.get("/api/session/bootstrap")

    assert response.status_code == 200
    payload = response.json()
    assert payload["auth_source"] == "local"
    assert payload["user"]["username"] == "test"
    assert payload["menu_tree"][0]["key"] == "compute"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation; .\\.venv\\Scripts\\python.exe -m pytest tests\\test_session_bootstrap.py -q`
Expected: FAIL because `backend.session_router` does not exist and `/api/session/bootstrap` is not mounted

- [ ] **Step 3: Write minimal bootstrap implementation**

```python
from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/session", tags=["session"])


def resolve_session_context(request: Request) -> dict:
    return {
        "user": {
            "user_id": 0,
            "username": "",
            "display_name": "",
            "is_admin": False,
        },
        "auth_source": "local",
        "capabilities": [],
        "menu_tree": [],
        "org_context": {},
    }


@router.get("/bootstrap")
def session_bootstrap(request: Request):
    return resolve_session_context(request)
```

```python
from backend.session_router import router as session_router

app.include_router(session_router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation; .\\.venv\\Scripts\\python.exe -m pytest tests\\test_session_bootstrap.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/session_router.py backend/identity_access.py backend/app.py tests/test_session_bootstrap.py
git commit -m "feat: add session bootstrap foundation"
```

### Task 3: Build the portal shell and navigation bootstrap

**Files:**
- Create: `portal_ui/src/router/index.ts`
- Create: `portal_ui/src/stores/session.ts`
- Create: `portal_ui/src/stores/navigation.ts`
- Create: `portal_ui/src/services/http.ts`
- Create: `portal_ui/src/services/api/session.ts`
- Create: `portal_ui/src/shell/PortalShell.vue`
- Create: `portal_ui/src/shell/PortalSidebar.vue`
- Create: `portal_ui/src/shell/PortalTopbar.vue`
- Create: `portal_ui/src/shell/PortalBreadcrumb.vue`
- Create: `portal_ui/src/modules/compute/index.ts`
- Create: `portal_ui/src/modules/compute/routes.ts`
- Create: `portal_ui/src/modules/compute/views/CommercialSoftwareView.vue`
- Create: `portal_ui/tests/unit/portal-shell.spec.ts`

- [ ] **Step 1: Write the failing shell navigation test**

```ts
import { describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import PortalShell from '../../src/shell/PortalShell.vue'

describe('PortalShell', () => {
  it('shows compute center as the default primary menu group', () => {
    setActivePinia(createPinia())

    const wrapper = mount(PortalShell, {
      global: {
        stubs: {
          RouterView: { template: '<div />' },
        },
      },
    })

    expect(wrapper.text()).toContain('计算资源')
    expect(wrapper.text()).toContain('商业软件')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm run test -- portal-shell.spec.ts`
Expected: FAIL because shell components and stores do not exist

- [ ] **Step 3: Write minimal shell implementation**

```ts
export const routes = [
  {
    path: '/',
    component: () => import('../shell/PortalShell.vue'),
    children: [
      {
        path: '',
        redirect: '/compute/commercial',
      },
      {
        path: '/compute/commercial',
        component: () => import('../modules/compute/views/CommercialSoftwareView.vue'),
      },
    ],
  },
]
```

```vue
<template>
  <div class="portal-shell">
    <PortalSidebar />
    <main class="portal-shell__main">
      <PortalTopbar />
      <PortalBreadcrumb />
      <RouterView />
    </main>
  </div>
</template>
```

```vue
<template>
  <aside>
    <div>计算资源</div>
    <div>商业软件</div>
    <div>仿真APP</div>
    <div>计算工具</div>
  </aside>
</template>
```

```vue
<template>
  <section>
    <h1>可用软件列表</h1>
    <p>Vue3 新壳已接管默认商业软件页。</p>
  </section>
</template>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm run test -- portal-shell.spec.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add portal_ui/src/router/index.ts portal_ui/src/stores/session.ts portal_ui/src/stores/navigation.ts portal_ui/src/services/http.ts portal_ui/src/services/api/session.ts portal_ui/src/shell/PortalShell.vue portal_ui/src/shell/PortalSidebar.vue portal_ui/src/shell/PortalTopbar.vue portal_ui/src/shell/PortalBreadcrumb.vue portal_ui/src/modules/compute/index.ts portal_ui/src/modules/compute/routes.ts portal_ui/src/modules/compute/views/CommercialSoftwareView.vue portal_ui/tests/unit/portal-shell.spec.ts
git commit -m "feat: add vue portal shell and default compute route"
```

### Task 4: Mount the Vue build under `/portal/` without breaking legacy pages

**Files:**
- Modify: `backend/app.py`
- Modify: `deploy/portal.Dockerfile`
- Create: `tests/test_portal_ui_mount.py`

- [ ] **Step 1: Write the failing mount test**

```python
from pathlib import Path


def test_portal_ui_mount_directory_exists():
    portal_dir = Path(__file__).resolve().parent.parent / "frontend" / "portal"
    assert portal_dir.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation; .\\.venv\\Scripts\\python.exe -m pytest tests\\test_portal_ui_mount.py -q`
Expected: FAIL because `frontend/portal` has not been built yet

- [ ] **Step 3: Wire static mounting**

```python
portal_ui_path = Path(__file__).parent.parent / "frontend" / "portal"
if portal_ui_path.exists():
    app.mount("/portal", StaticFiles(directory=str(portal_ui_path), html=True), name="portal-ui")
```

```dockerfile
COPY frontend/ ./frontend/
```

- [ ] **Step 4: Run build and verify**

Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm run build`
Expected: `frontend/portal` generated

Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation; .\\.venv\\Scripts\\python.exe -m pytest tests\\test_portal_ui_mount.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app.py deploy/portal.Dockerfile tests/test_portal_ui_mount.py frontend/portal
git commit -m "feat: mount vue portal build under portal path"
```

---

## Self-Review

- **Spec coverage:** This first-slice plan intentionally covers only the foundation: Vue3 workspace, shell, session bootstrap, and legacy-safe `/portal/` mounting. It does not yet implement workspace move, booking register, case publish packages, SDK center, or stats dashboards; those belong in follow-up plans after the shell is stable.
- **Placeholder scan:** No `TODO`, `TBD`, or “similar to task” references remain.
- **Type consistency:** The bootstrap contract consistently uses `user`, `auth_source`, `capabilities`, `menu_tree`, and `org_context`.

## Execution Handoff

Plan saved to `docs/superpowers/plans/2026-04-13-vue3-portal-shell-foundation.md`.

Execution mode is already chosen by the user: **Subagent-Driven Development**.
