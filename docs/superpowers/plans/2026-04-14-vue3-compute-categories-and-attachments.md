# Vue3 Compute Categories and App Attachments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended). Steps use checkbox (`- [ ]`) syntax for tracking. Do **not** commit during execution because this repo's instructions forbid unrequested commits.

**Goal:** Make `仿真APP` and `计算工具` pages consume real classified data, and replace App detail placeholder tabs with a real backend-driven attachments interface for 教程文档 / 视频资源 / 插件下载.

**Architecture:** Reuse the existing compute store and `/api/remote-apps/` list as the single data source for category pages, now that `app_kind` is returned by the backend. Introduce a pool-scoped attachment model and read-only API so App detail resolves real content by `pool_id`, keeping launch behavior unchanged while making the detail page genuinely useful.

**Tech Stack:** Vue 3, Pinia, Vue Router, Axios, Vitest, FastAPI, pytest, MySQL schema migrations.

---

### Task 1: Turn `仿真APP` and `计算工具` into real category pages

**Files:**
- Modify: `portal_ui/src/modules/compute/views/SimulationAppView.vue`
- Modify: `portal_ui/src/modules/compute/views/ComputeToolsView.vue`
- Create: `portal_ui/tests/unit/simulation-app-view.spec.ts`
- Create: `portal_ui/tests/unit/compute-tools-view.spec.ts`

- [ ] **Step 1: Write the failing category view tests**

```ts
import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it } from 'vitest'

import ComputeToolsView from '@/modules/compute/views/ComputeToolsView.vue'
import SimulationAppView from '@/modules/compute/views/SimulationAppView.vue'
import { useComputeStore } from '@/stores/compute'

const apps = [
  { id: 1, pool_id: 10, app_kind: 'simulation_app', name: '仿真脚本平台', icon: 'terminal', protocol: 'rdp', supports_gui: true, supports_script: true, script_runtime_id: 1, script_profile_key: 'solver', script_profile_name: 'Solver', script_schedulable: true, script_status_code: 'ready', script_status_label: '可调度', script_status_tone: 'success', script_status_summary: '', script_status_reason: '', resource_status_code: 'available', resource_status_label: '可用', resource_status_tone: 'success', active_count: 0, queued_count: 0, max_concurrent: 1, has_capacity: true },
  { id: 2, pool_id: 11, app_kind: 'compute_tool', name: '热力学计算器', icon: 'calculate', protocol: 'rdp', supports_gui: true, supports_script: false, script_runtime_id: null, script_profile_key: null, script_profile_name: null, script_schedulable: false, script_status_code: '', script_status_label: '', script_status_tone: '', script_status_summary: '', script_status_reason: '', resource_status_code: 'available', resource_status_label: '可用', resource_status_tone: 'success', active_count: 0, queued_count: 0, max_concurrent: 1, has_capacity: true },
]

describe('category views', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    const store = useComputeStore()
    store.apps = apps as never
  })

  it('simulation page only renders simulation_app cards', () => {
    const wrapper = mount(SimulationAppView, {
      global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
    })

    expect(wrapper.text()).toContain('仿真脚本平台')
    expect(wrapper.text()).not.toContain('热力学计算器')
  })

  it('compute tools page only renders compute_tool cards', () => {
    const wrapper = mount(ComputeToolsView, {
      global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
    })

    expect(wrapper.text()).toContain('热力学计算器')
    expect(wrapper.text()).not.toContain('仿真脚本平台')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm run test -- simulation-app-view.spec.ts compute-tools-view.spec.ts`
Expected: FAIL because both views still render static placeholder text instead of classified cards

- [ ] **Step 3: Implement the minimal real category pages**

```vue
<template>
  <section class="compute-view">
    <header>
      <h1>仿真应用列表</h1>
      <p>展示当前账号可访问的仿真应用资源。</p>
    </header>
    <AppFilterBar v-model="computeStore.query" />
    <div v-if="items.length === 0" class="compute-view__empty">暂无仿真应用</div>
    <div v-else class="compute-view__grid">
      <AppCard v-for="app in items" :key="app.pool_id" :app="app" />
    </div>
  </section>
</template>
```

```ts
const items = computed(() =>
  computeStore.filteredApps.filter((app) => app.app_kind === 'simulation_app'),
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm run test -- simulation-app-view.spec.ts compute-tools-view.spec.ts`
Expected: PASS

### Task 2: Add a real backend attachment API for App detail

**Files:**
- Create: `backend/app_attachment_router.py`
- Create: `backend/app_attachment_service.py`
- Modify: `backend/app.py`
- Create: `database/migrate_app_attachment.sql`
- Modify: `database/init.sql`
- Modify: `deploy/initdb/01-portal-init.sql`
- Create: `tests/test_app_attachment_router.py`

- [ ] **Step 1: Write the failing backend attachment tests**

```python
import asyncio
from types import SimpleNamespace

import httpx
from fastapi import FastAPI

import backend.app_attachment_router as attachment_router
from backend.models import UserInfo


def _request(app: FastAPI, path: str):
    async def _run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get(path)
    return asyncio.run(_run())


def test_pool_attachments_group_by_kind(monkeypatch):
    monkeypatch.setattr(
        attachment_router,
        'attachment_service',
        SimpleNamespace(
            get_pool_attachments=lambda pool_id, user_id: {
                'pool_id': pool_id,
                'tutorial_docs': [{'id': 1, 'title': '用户手册', 'summary': 'PDF', 'link_url': 'https://example/doc.pdf'}],
                'video_resources': [{'id': 2, 'title': '演示视频', 'summary': 'MP4', 'link_url': 'https://example/video'}],
                'plugin_downloads': [{'id': 3, 'title': '插件包', 'summary': 'ZIP', 'link_url': 'https://example/plugin.zip'}],
            }
        ),
    )

    app = FastAPI()
    app.include_router(attachment_router.router)
    app.dependency_overrides[attachment_router.get_current_user] = lambda: UserInfo(
        user_id=7, username='tester', display_name='Tester', is_admin=False
    )

    response = _request(app, '/api/app-attachments/pools/10')

    assert response.status_code == 200
    payload = response.json()
    assert payload['pool_id'] == 10
    assert payload['tutorial_docs'][0]['title'] == '用户手册'
    assert payload['video_resources'][0]['title'] == '演示视频'
    assert payload['plugin_downloads'][0]['title'] == '插件包'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation; D:\Nercar\NanGang\PSD\Apps\gucamole_app\.venv\Scripts\python.exe -m pytest tests\test_app_attachment_router.py -q`
Expected: FAIL because router/service do not exist

- [ ] **Step 3: Implement the minimal attachment backend**

```python
class AppAttachmentItem(BaseModel):
    id: int
    title: str
    summary: str = ""
    link_url: str


class PoolAttachmentResponse(BaseModel):
    pool_id: int
    tutorial_docs: list[AppAttachmentItem] = Field(default_factory=list)
    video_resources: list[AppAttachmentItem] = Field(default_factory=list)
    plugin_downloads: list[AppAttachmentItem] = Field(default_factory=list)
```

```python
router = APIRouter(prefix="/api/app-attachments", tags=["app-attachments"])

@router.get("/pools/{pool_id}", response_model=PoolAttachmentResponse)
def get_pool_attachments(pool_id: int, user: UserInfo = Depends(get_current_user)):
    return attachment_service.get_pool_attachments(pool_id=pool_id, user_id=user.user_id)
```

```sql
CREATE TABLE IF NOT EXISTS app_attachment (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    pool_id BIGINT NOT NULL,
    attachment_kind VARCHAR(30) NOT NULL COMMENT 'tutorial_doc/video_resource/plugin_download',
    title VARCHAR(200) NOT NULL,
    summary VARCHAR(500) DEFAULT '',
    link_url VARCHAR(1000) NOT NULL,
    sort_order INT NOT NULL DEFAULT 0,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_app_attachment_pool_kind (pool_id, attachment_kind, is_active, sort_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

- [ ] **Step 4: Run backend tests to verify they pass**

Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation; D:\Nercar\NanGang\PSD\Apps\gucamole_app\.venv\Scripts\python.exe -m pytest tests\test_app_attachment_router.py -q`
Expected: PASS

### Task 3: Replace App detail placeholder tabs with real attachment data

**Files:**
- Modify: `portal_ui/src/types/compute.ts`
- Modify: `portal_ui/src/services/api/compute.ts`
- Modify: `portal_ui/src/modules/compute/views/AppDetailView.vue`
- Create: `portal_ui/tests/unit/app-detail-attachments.spec.ts`

- [ ] **Step 1: Write the failing attachment view test**

```ts
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory } from 'vue-router'

import * as computeApi from '@/services/api/compute'
import AppDetailView from '@/modules/compute/views/AppDetailView.vue'
import { createPortalRouter } from '@/router'
import { useComputeStore } from '@/stores/compute'

describe('AppDetailView attachments', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('renders grouped attachment content from backend', async () => {
    const store = useComputeStore()
    store.apps = [{
      id: 1, pool_id: 10, app_kind: 'commercial_software', name: 'ANSYS Fluent', icon: 'desktop', protocol: 'rdp',
      supports_gui: true, supports_script: true, script_runtime_id: 1, script_profile_key: 'ansys', script_profile_name: 'ANSYS',
      script_schedulable: true, script_status_code: 'ready', script_status_label: '可调度', script_status_tone: 'success',
      script_status_summary: '', script_status_reason: '', resource_status_code: 'available', resource_status_label: '可用',
      resource_status_tone: 'success', active_count: 0, queued_count: 0, max_concurrent: 2, has_capacity: true
    }] as never
    store.loaded = true
    vi.spyOn(computeApi, 'getPoolAttachments').mockResolvedValue({
      data: {
        pool_id: 10,
        tutorial_docs: [{ id: 1, title: '用户手册', summary: 'PDF', link_url: 'https://example/doc.pdf' }],
        video_resources: [{ id: 2, title: '演示视频', summary: 'MP4', link_url: 'https://example/video' }],
        plugin_downloads: [{ id: 3, title: '插件包', summary: 'ZIP', link_url: 'https://example/plugin.zip' }],
      },
      headers: {},
    } as never)

    const router = createPortalRouter(createMemoryHistory())
    router.push('/compute/pools/10')
    await router.isReady()

    const wrapper = mount(AppDetailView, {
      global: {
        plugins: [router],
        stubs: { RouterLink: { template: '<a><slot /></a>' } },
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('用户手册')
    expect(wrapper.text()).toContain('演示视频')
    expect(wrapper.text()).toContain('插件包')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm run test -- app-detail-attachments.spec.ts`
Expected: FAIL because detail view still only renders static tab chips

- [ ] **Step 3: Implement minimal attachment rendering**

```ts
export type AttachmentItem = {
  id: number
  title: string
  summary: string
  link_url: string
}

export type PoolAttachmentResponse = {
  pool_id: number
  tutorial_docs: AttachmentItem[]
  video_resources: AttachmentItem[]
  plugin_downloads: AttachmentItem[]
}
```

```ts
export function getPoolAttachments(poolId: number) {
  return http.get<PoolAttachmentResponse>(`/api/app-attachments/pools/${poolId}`)
}
```

```vue
<section class="app-detail__attachments">
  <div v-if="attachmentsLoading">附件加载中...</div>
  <div v-else-if="attachmentsError">{{ attachmentsError }}</div>
  <template v-else>
    <div>
      <h2>教程文档</h2>
      <a v-for="item in attachments.tutorial_docs" :key="item.id" :href="item.link_url" target="_blank" rel="noreferrer">{{ item.title }}</a>
    </div>
    <div>
      <h2>视频资源</h2>
      <a v-for="item in attachments.video_resources" :key="item.id" :href="item.link_url" target="_blank" rel="noreferrer">{{ item.title }}</a>
    </div>
    <div>
      <h2>插件下载</h2>
      <a v-for="item in attachments.plugin_downloads" :key="item.id" :href="item.link_url" target="_blank" rel="noreferrer">{{ item.title }}</a>
    </div>
  </template>
</section>
```

- [ ] **Step 4: Run frontend tests to verify they pass**

Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm run test -- app-detail-attachments.spec.ts simulation-app-view.spec.ts compute-tools-view.spec.ts`
Expected: PASS

### Final verification

- [ ] **Step 1: Run backend verification**

Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation; D:\Nercar\NanGang\PSD\Apps\gucamole_app\.venv\Scripts\python.exe -m pytest tests\test_session_bootstrap.py tests\test_portal_ui_spa_fallback.py tests\test_app_kind_semantics.py tests\test_router_drive_transfer_policy.py tests\test_app_attachment_router.py -q`
Expected: PASS

- [ ] **Step 2: Run frontend verification**

Run: `cd D:\Nercar\NanGang\PSD\Apps\gucamole_app\.worktrees\renaissance-ai-vue3-portal-shell-foundation\portal_ui; npm run test && npm run typecheck && npm run build`
Expected: PASS

---

## Self-Review

- **Spec coverage:** This plan closes phase 4 on both sides: real category pages for 仿真APP / 计算工具, plus a real attachment interface for App detail.
- **Placeholder scan:** No placeholders remain.
- **Type consistency:** Pool-scoped detail and attachment API both use `pool_id` as the stable identifier.

## Execution Handoff

Plan saved to `docs/superpowers/plans/2026-04-14-vue3-compute-categories-and-attachments.md`.

Execution mode is already chosen by the user: **Subagent-Driven Development**.
