# Vue3 Session and Navigation Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Vue3 portal shell consume the real bootstrap contract so authentication state, current user, menu tree, breadcrumb, and topbar are driven by backend session context instead of hard-coded placeholders.

**Architecture:** Keep the backend bootstrap endpoint stable and move the frontend shell to a single source of truth: a `session` store hydrated from `/api/session/bootstrap`, with `navigation` derived from the returned `menu_tree`. HTTP transport owns `Authorization` injection and `refresh-token` rotation, while the shell only renders store state.

**Tech Stack:** Vue 3, Vite, Vue Router, Pinia, Axios, Vitest, FastAPI, pytest.

---

### Task 1: Hydrate the Vue shell from session bootstrap

**Files:**
- Create: `portal_ui/src/types/auth.ts`
- Create: `portal_ui/src/constants/auth.ts`
- Modify: `portal_ui/src/services/http.ts`
- Modify: `portal_ui/src/services/api/session.ts`
- Modify: `portal_ui/src/stores/session.ts`
- Modify: `portal_ui/src/bootstrap.ts`
- Create: `portal_ui/tests/unit/session-store.spec.ts`
- Create: `portal_ui/tests/unit/http.spec.ts`

- [ ] **Step 1: Write the failing session bootstrap store test**

```ts
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useSessionStore } from '@/stores/session'
import * as sessionApi from '@/services/api/session'

describe('session store bootstrap', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
  })

  it('hydrates authenticated user context from backend bootstrap', async () => {
    localStorage.setItem('portal_token', 'token-a')
    vi.spyOn(sessionApi, 'getSessionBootstrap').mockResolvedValue({
      data: {
        authenticated: true,
        auth_source: 'local',
        user: {
          user_id: 7,
          username: 'alice',
          display_name: 'Alice',
          is_admin: false,
        },
        capabilities: ['compute.view', 'ops.app.view'],
        menu_tree: [
          {
            key: 'compute',
            title: '计算资源',
            children: [{ key: 'compute-commercial', title: '商业软件', path: '/compute/commercial' }],
          },
        ],
        org_context: { department: '研发' },
      },
      headers: {},
    } as never)

    const store = useSessionStore()
    await store.bootstrap()

    expect(store.authenticated).toBe(true)
    expect(store.user?.username).toBe('alice')
    expect(store.menuTree[0].key).toBe('compute')
    expect(store.capabilities).toContain('ops.app.view')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm run test -- session-store.spec.ts`
Expected: FAIL because `session` store does not expose `bootstrap`, `user`, `capabilities`, or `menuTree`

- [ ] **Step 3: Write the failing HTTP transport behavior test**

```ts
import { afterEach, describe, expect, it, vi } from 'vitest'

describe('http transport', () => {
  afterEach(() => {
    vi.resetModules()
    localStorage.clear()
  })

  it('adds bearer token and rotates refresh-token from response headers', async () => {
    localStorage.setItem('portal_token', 'old-token')

    const httpModule = await import('@/services/http')
    const http = httpModule.default

    const requestHandler = (http.interceptors.request as any).handlers[0].fulfilled
    const responseHandler = (http.interceptors.response as any).handlers[0].fulfilled

    const config = await requestHandler({ headers: {} })
    expect(config.headers.Authorization).toBe('Bearer old-token')

    await responseHandler({
      headers: {
        'refresh-token': 'new-token',
      },
      data: {},
    })

    expect(localStorage.getItem('portal_token')).toBe('new-token')
  })
})
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm run test -- http.spec.ts`
Expected: FAIL because `services/http.ts` has no interceptors and no token rotation behavior

- [ ] **Step 5: Write minimal implementation**

```ts
export type SessionUser = {
  user_id: number
  username: string
  display_name: string
  is_admin: boolean
}

export type SessionMenuNode = {
  key: string
  title: string
  path?: string
  children?: SessionMenuNode[]
}

export type SessionBootstrapPayload = {
  authenticated: boolean
  auth_source: string
  user: SessionUser | null
  capabilities: string[]
  menu_tree: SessionMenuNode[]
  org_context: Record<string, unknown>
}
```

```ts
const TOKEN_KEY = 'portal_token'
const USER_KEY = 'portal_user'
```

```ts
http.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

http.interceptors.response.use((response) => {
  const nextToken = response.headers?.['refresh-token']
  if (typeof nextToken === 'string' && nextToken) {
    localStorage.setItem(TOKEN_KEY, nextToken)
  }
  return response
})
```

```ts
export function getSessionBootstrap() {
  return http.get<SessionBootstrapPayload>('/api/session/bootstrap')
}
```

```ts
const authenticated = ref(false)
const authSource = ref('anonymous')
const user = ref<SessionUser | null>(null)
const capabilities = ref<string[]>([])
const menuTree = ref<SessionMenuNode[]>([])
const orgContext = ref<Record<string, unknown>>({})
const bootstrapLoaded = ref(false)

async function bootstrap() {
  const response = await getSessionBootstrap()
  const payload = response.data
  authenticated.value = payload.authenticated
  authSource.value = payload.auth_source
  user.value = payload.user
  capabilities.value = payload.capabilities
  menuTree.value = payload.menu_tree
  orgContext.value = payload.org_context
  bootstrapLoaded.value = true
  if (payload.user) {
    localStorage.setItem(USER_KEY, JSON.stringify(payload.user))
  } else {
    localStorage.removeItem(USER_KEY)
  }
}
```

```ts
export async function bootstrapPortalApp(activeRouter: Router = router) {
  const app = createPortalApp(activeRouter)
  const pinia = createPinia()
  app.use(pinia)
  app.use(activeRouter)

  const sessionStore = useSessionStore(pinia)
  await sessionStore.bootstrap()
  return { app, pinia, sessionStore }
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm run test -- session-store.spec.ts http.spec.ts`
Expected: PASS

- [ ] **Step 7: Run typecheck**

Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm run typecheck`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add portal_ui/src/types/auth.ts portal_ui/src/constants/auth.ts portal_ui/src/services/http.ts portal_ui/src/services/api/session.ts portal_ui/src/stores/session.ts portal_ui/src/bootstrap.ts portal_ui/tests/unit/session-store.spec.ts portal_ui/tests/unit/http.spec.ts
git commit -m "feat: hydrate vue shell from session bootstrap"
```

### Task 2: Drive shell navigation, breadcrumb, and topbar from bootstrap state

**Files:**
- Modify: `portal_ui/src/stores/navigation.ts`
- Modify: `portal_ui/src/shell/PortalSidebar.vue`
- Modify: `portal_ui/src/shell/PortalTopbar.vue`
- Modify: `portal_ui/src/shell/PortalBreadcrumb.vue`
- Modify: `portal_ui/src/shell/PortalShell.vue`
- Modify: `portal_ui/src/router/index.ts`
- Create: `portal_ui/tests/unit/navigation-store.spec.ts`
- Modify: `portal_ui/tests/unit/portal-shell.spec.ts`
- Modify: `portal_ui/tests/unit/bootstrap.spec.ts`

- [ ] **Step 1: Write the failing navigation store test**

```ts
import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useNavigationStore } from '@/stores/navigation'
import { useSessionStore } from '@/stores/session'

describe('navigation store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('derives breadcrumb and default path from bootstrap menu tree', () => {
    const sessionStore = useSessionStore()
    sessionStore.$patch({
      menuTree: [
        {
          key: 'compute',
          title: '计算资源',
          children: [{ key: 'compute-commercial', title: '商业软件', path: '/compute/commercial' }],
        },
      ],
    })

    const navigationStore = useNavigationStore()

    expect(navigationStore.defaultPath).toBe('/compute/commercial')
    expect(navigationStore.resolveBreadcrumb('/compute/commercial')).toEqual(['计算资源', '商业软件'])
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm run test -- navigation-store.spec.ts`
Expected: FAIL because navigation store still uses a hard-coded `MENU_TREE`

- [ ] **Step 3: Write the failing shell integration test**

```ts
import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it } from 'vitest'
import { createMemoryHistory } from 'vue-router'

import { createPortalRouter } from '@/router'
import PortalShell from '@/shell/PortalShell.vue'
import { useSessionStore } from '@/stores/session'

describe('PortalShell dynamic chrome', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders authenticated user name and bootstrap menu labels', async () => {
    const router = createPortalRouter(createMemoryHistory())
    router.push('/compute/commercial')
    await router.isReady()

    const sessionStore = useSessionStore()
    sessionStore.$patch({
      authenticated: true,
      user: {
        user_id: 1,
        username: 'admin',
        display_name: '管理员',
        is_admin: true,
      },
      menuTree: [
        {
          key: 'compute',
          title: '计算资源',
          children: [{ key: 'compute-commercial', title: '商业软件', path: '/compute/commercial' }],
        },
      ],
    })

    const wrapper = mount(PortalShell, {
      global: {
        plugins: [router],
      },
    })

    expect(wrapper.text()).toContain('管理员')
    expect(wrapper.text()).toContain('计算资源')
    expect(wrapper.text()).toContain('商业软件')
  })
})
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm run test -- portal-shell.spec.ts bootstrap.spec.ts`
Expected: FAIL because shell still renders hard-coded topbar/breadcrumb/navigation and bootstrap path is not the single source of truth

- [ ] **Step 5: Write minimal implementation**

```ts
const sessionStore = useSessionStore()

const menuTree = computed(() => sessionStore.menuTree)
const defaultPath = computed(() => {
  const firstGroup = menuTree.value[0]
  const firstChild = firstGroup?.children?.[0]
  return firstChild?.path || '/compute/commercial'
})

function resolveBreadcrumb(path: string): string[] {
  for (const group of menuTree.value) {
    for (const child of group.children || []) {
      if (child.path === path) return [group.title, child.title]
    }
    if (group.path === path) return [group.title]
  }
  return []
}
```

```vue
<template>
  <aside class="sidebar">
    <section v-for="group in menuTree" :key="group.key" class="sidebar__group">
      <div class="sidebar__group-title">{{ group.title }}</div>
      <RouterLink
        v-for="child in group.children || []"
        :key="child.key"
        :to="child.path || '/'"
        class="sidebar__item"
        active-class="sidebar__item--active"
      >
        {{ child.title }}
      </RouterLink>
    </section>
  </aside>
</template>
```

```vue
<template>
  <header class="topbar">
    <div class="topbar__title">南钢-仿真</div>
    <div class="topbar__user">{{ sessionStore.user?.display_name || '未登录' }}</div>
  </header>
</template>
```

```ts
router.beforeEach(async (to) => {
  const sessionStore = useSessionStore()
  if (!sessionStore.bootstrapLoaded) {
    await sessionStore.bootstrap()
  }
  if (to.path === '/') {
    const navigationStore = useNavigationStore()
    return navigationStore.defaultPath
  }
  return true
})
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm run test -- navigation-store.spec.ts portal-shell.spec.ts bootstrap.spec.ts`
Expected: PASS

- [ ] **Step 7: Run full frontend verification**

Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm run test && npm run typecheck && npm run build`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add portal_ui/src/stores/navigation.ts portal_ui/src/shell/PortalSidebar.vue portal_ui/src/shell/PortalTopbar.vue portal_ui/src/shell/PortalBreadcrumb.vue portal_ui/src/shell/PortalShell.vue portal_ui/src/router/index.ts portal_ui/tests/unit/navigation-store.spec.ts portal_ui/tests/unit/portal-shell.spec.ts portal_ui/tests/unit/bootstrap.spec.ts
git commit -m "feat: drive vue shell chrome from bootstrap state"
```

---

## Self-Review

- **Spec coverage:** This plan covers the real second phase boundary: session bootstrap integration, dynamic navigation, breadcrumb, topbar, and route bootstrap. It intentionally does not start fetching `/api/remote-apps/` cards yet; that belongs to the next phase (`计算资源真实列表接线`).
- **Placeholder scan:** No placeholders or “similar to task” shortcuts remain.
- **Type consistency:** Session payload uses `authenticated`, `auth_source`, `user`, `capabilities`, `menu_tree`, and `org_context` consistently across store, API, and shell.

## Execution Handoff

Plan saved to `docs/superpowers/plans/2026-04-14-vue3-session-navigation-integration.md`.

Execution mode is already chosen by the user: **Subagent-Driven Development**.
