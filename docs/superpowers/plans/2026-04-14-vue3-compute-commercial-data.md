# Vue3 Compute Commercial Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `计算资源 / 商业软件` placeholder with a real Vue3 data flow backed by `/api/remote-apps/`, including cards, search, status display, and a first App detail route shell.

**Architecture:** Keep the existing RemoteApp launch backend untouched and add a typed Vue data layer on top of `/api/remote-apps/`. The compute module owns resource listing state and rendering, while App detail initially reuses the list API to locate a selected app and exposes content tabs as stable placeholders for later attachment APIs.

**Tech Stack:** Vue 3, Vue Router, Pinia, Axios, Vitest, FastAPI existing `/api/remote-apps/`.

---

### Task 1: Add typed compute data layer

**Files:**
- Create: `portal_ui/src/types/compute.ts`
- Create: `portal_ui/src/services/api/compute.ts`
- Create: `portal_ui/src/stores/compute.ts`
- Create: `portal_ui/tests/unit/compute-store.spec.ts`

- [ ] **Step 1: Write the failing compute store test**

```ts
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import * as computeApi from '@/services/api/compute'
import { useComputeStore } from '@/stores/compute'

describe('compute store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('loads remote app cards and filters by fuzzy name', async () => {
    vi.spyOn(computeApi, 'listRemoteApps').mockResolvedValue({
      data: [
        {
          id: 1,
          pool_id: 10,
          name: 'ANSYS Fluent',
          icon: 'desktop',
          protocol: 'rdp',
          supports_gui: true,
          supports_script: true,
          script_runtime_id: 1,
          script_profile_key: 'ansys_mapdl',
          script_profile_name: 'ANSYS MAPDL',
          script_schedulable: true,
          script_status_code: 'ready',
          script_status_label: '可调度',
          script_status_tone: 'success',
          script_status_summary: 'Worker 就绪',
          script_status_reason: '',
          resource_status_code: 'available',
          resource_status_label: '可用',
          resource_status_tone: 'success',
          active_count: 0,
          queued_count: 0,
          max_concurrent: 2,
          has_capacity: true,
        },
        {
          id: 2,
          pool_id: 11,
          name: 'COMSOL Multiphysics',
          icon: 'desktop',
          protocol: 'rdp',
          supports_gui: true,
          supports_script: false,
          script_runtime_id: null,
          script_profile_key: null,
          script_profile_name: null,
          script_schedulable: false,
          script_status_code: '',
          script_status_label: '',
          script_status_tone: '',
          script_status_summary: '',
          script_status_reason: '',
          resource_status_code: 'busy',
          resource_status_label: '忙碌',
          resource_status_tone: 'warning',
          active_count: 2,
          queued_count: 1,
          max_concurrent: 2,
          has_capacity: false,
        },
      ],
      headers: {},
    } as never)

    const store = useComputeStore()
    await store.loadApps()
    store.query = 'fluent'

    expect(store.apps).toHaveLength(2)
    expect(store.filteredApps.map((app) => app.name)).toEqual(['ANSYS Fluent'])
    expect(store.getAppById(2)?.name).toBe('COMSOL Multiphysics')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm run test -- compute-store.spec.ts`
Expected: FAIL because compute types/API/store do not exist

- [ ] **Step 3: Implement minimal typed data layer**

```ts
export type ComputeAppCard = {
  id: number
  pool_id: number
  name: string
  icon: string
  protocol: string
  supports_gui: boolean
  supports_script: boolean
  script_runtime_id: number | null
  script_profile_key: string | null
  script_profile_name: string | null
  script_schedulable: boolean
  script_status_code: string
  script_status_label: string
  script_status_tone: string
  script_status_summary: string
  script_status_reason: string
  resource_status_code: string
  resource_status_label: string
  resource_status_tone: string
  active_count: number
  queued_count: number
  max_concurrent: number
  has_capacity: boolean
}
```

```ts
export function listRemoteApps() {
  return http.get<ComputeAppCard[]>('/api/remote-apps/')
}
```

```ts
const apps = ref<ComputeAppCard[]>([])
const query = ref('')
const loading = ref(false)
const errorMessage = ref('')

const filteredApps = computed(() => {
  const keyword = query.value.trim().toLowerCase()
  if (!keyword) return apps.value
  return apps.value.filter((app) => app.name.toLowerCase().includes(keyword))
})

async function loadApps() {
  loading.value = true
  errorMessage.value = ''
  try {
    const response = await listRemoteApps()
    apps.value = response.data
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '加载应用失败'
  } finally {
    loading.value = false
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm run test -- compute-store.spec.ts`
Expected: PASS

### Task 2: Render the commercial software list from compute store

**Files:**
- Create: `portal_ui/src/modules/compute/components/AppCard.vue`
- Create: `portal_ui/src/modules/compute/components/AppFilterBar.vue`
- Modify: `portal_ui/src/modules/compute/views/CommercialSoftwareView.vue`
- Create: `portal_ui/tests/unit/commercial-software-view.spec.ts`

- [ ] **Step 1: Write the failing view test**

```ts
import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it } from 'vitest'

import CommercialSoftwareView from '@/modules/compute/views/CommercialSoftwareView.vue'
import { useComputeStore } from '@/stores/compute'

describe('CommercialSoftwareView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders loaded app cards and filters by search text', async () => {
    const store = useComputeStore()
    store.apps = [
      {
        id: 1,
        pool_id: 10,
        name: 'ANSYS Fluent',
        icon: 'desktop',
        protocol: 'rdp',
        supports_gui: true,
        supports_script: true,
        script_runtime_id: 1,
        script_profile_key: 'ansys_mapdl',
        script_profile_name: 'ANSYS MAPDL',
        script_schedulable: true,
        script_status_code: 'ready',
        script_status_label: '可调度',
        script_status_tone: 'success',
        script_status_summary: 'Worker 就绪',
        script_status_reason: '',
        resource_status_code: 'available',
        resource_status_label: '可用',
        resource_status_tone: 'success',
        active_count: 0,
        queued_count: 0,
        max_concurrent: 2,
        has_capacity: true,
      },
      {
        id: 2,
        pool_id: 11,
        name: 'COMSOL Multiphysics',
        icon: 'desktop',
        protocol: 'rdp',
        supports_gui: true,
        supports_script: false,
        script_runtime_id: null,
        script_profile_key: null,
        script_profile_name: null,
        script_schedulable: false,
        script_status_code: '',
        script_status_label: '',
        script_status_tone: '',
        script_status_summary: '',
        script_status_reason: '',
        resource_status_code: 'busy',
        resource_status_label: '忙碌',
        resource_status_tone: 'warning',
        active_count: 2,
        queued_count: 1,
        max_concurrent: 2,
        has_capacity: false,
      },
    ]

    const wrapper = mount(CommercialSoftwareView, {
      global: {
        stubs: {
          RouterLink: { template: '<a><slot /></a>' },
        },
      },
    })

    expect(wrapper.text()).toContain('ANSYS Fluent')
    expect(wrapper.text()).toContain('COMSOL Multiphysics')

    await wrapper.find('input[type=\"search\"]').setValue('comsol')

    expect(wrapper.text()).not.toContain('ANSYS Fluent')
    expect(wrapper.text()).toContain('COMSOL Multiphysics')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm run test -- commercial-software-view.spec.ts`
Expected: FAIL because view still renders placeholder content and components do not exist

- [ ] **Step 3: Implement minimal list UI**

```vue
<template>
  <section class="commercial-view">
    <header>
      <h1>可用软件列表</h1>
      <p>展示当前账号可访问的商业软件资源池。</p>
    </header>
    <AppFilterBar v-model="computeStore.query" />
    <div class="commercial-view__grid">
      <AppCard v-for="app in computeStore.filteredApps" :key="app.id" :app="app" />
    </div>
  </section>
</template>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm run test -- commercial-software-view.spec.ts`
Expected: PASS

### Task 3: Add App detail route shell with attachment tabs

**Files:**
- Create: `portal_ui/src/modules/compute/views/AppDetailView.vue`
- Modify: `portal_ui/src/modules/compute/routes.ts`
- Modify: `portal_ui/src/stores/navigation.ts`
- Create: `portal_ui/tests/unit/app-detail-view.spec.ts`

- [ ] **Step 1: Write the failing detail route test**

```ts
import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it } from 'vitest'
import { createMemoryHistory } from 'vue-router'

import AppDetailView from '@/modules/compute/views/AppDetailView.vue'
import { createPortalRouter } from '@/router'
import { useComputeStore } from '@/stores/compute'

describe('AppDetailView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders app detail and attachment tab placeholders', async () => {
    const store = useComputeStore()
    store.apps = [
      {
        id: 1,
        pool_id: 10,
        name: 'ANSYS Fluent',
        icon: 'desktop',
        protocol: 'rdp',
        supports_gui: true,
        supports_script: true,
        script_runtime_id: 1,
        script_profile_key: 'ansys_mapdl',
        script_profile_name: 'ANSYS MAPDL',
        script_schedulable: true,
        script_status_code: 'ready',
        script_status_label: '可调度',
        script_status_tone: 'success',
        script_status_summary: 'Worker 就绪',
        script_status_reason: '',
        resource_status_code: 'available',
        resource_status_label: '可用',
        active_count: 0,
        queued_count: 0,
        max_concurrent: 2,
        has_capacity: true,
      },
    ]
    const router = createPortalRouter(createMemoryHistory())
    router.push('/compute/apps/1')
    await router.isReady()

    const wrapper = mount(AppDetailView, {
      global: {
        plugins: [router],
      },
    })

    expect(wrapper.text()).toContain('ANSYS Fluent')
    expect(wrapper.text()).toContain('教程文档')
    expect(wrapper.text()).toContain('视频资源')
    expect(wrapper.text()).toContain('插件下载')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm run test -- app-detail-view.spec.ts`
Expected: FAIL because detail view and route do not exist

- [ ] **Step 3: Implement minimal detail view**

```vue
<template>
  <section class="app-detail">
    <RouterLink to="/compute/commercial">返回列表</RouterLink>
    <h1>{{ app?.name || '应用不存在' }}</h1>
    <div class="app-detail__tabs">
      <span>概览</span>
      <span>启动使用</span>
      <span>脚本模式</span>
      <span>教程文档</span>
      <span>视频资源</span>
      <span>插件下载</span>
      <span>相关案例</span>
      <span>评论</span>
    </div>
  </section>
</template>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm run test -- app-detail-view.spec.ts`
Expected: PASS

### Final verification

- [ ] **Step 1: Run frontend tests**

Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm run test`
Expected: PASS

- [ ] **Step 2: Run frontend typecheck**

Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm run typecheck`
Expected: PASS

- [ ] **Step 3: Run frontend build**

Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm run build`
Expected: PASS

---

## Self-Review

- **Spec coverage:** This plan connects the commercial software page to real remote-app data, adds search/card rendering, and introduces the App detail shell for later attachments. It intentionally does not migrate the launch window yet; that deserves its own focused plan because it touches Guacamole session behavior.
- **Placeholder scan:** No TBD/TODO placeholders remain.
- **Type consistency:** Store, API, and view use one `ComputeAppCard` shape aligned to `ResourcePoolCardResponse`.

## Execution Handoff

Plan saved to `docs/superpowers/plans/2026-04-14-vue3-compute-commercial-data.md`.

Execution mode is already chosen by the user: **Subagent-Driven Development**.
