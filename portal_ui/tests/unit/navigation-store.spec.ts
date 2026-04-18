import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { useNavigationStore } from '@/stores/navigation'
import { useSessionStore } from '@/stores/session'

describe('navigation store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('does not invent a fallback menu when bootstrap menu tree is empty', () => {
    const navigationStore = useNavigationStore()

    expect(navigationStore.menuTree).toEqual([])
    expect(navigationStore.defaultPath).toBeUndefined()
    expect(navigationStore.resolveBreadcrumb('/compute/pools/10')).toEqual([])
  })

  it('derives default path and breadcrumb from bootstrap menu tree', () => {
    const sessionStore = useSessionStore()
    sessionStore.$patch({
      menuTree: [
        {
          key: 'custom',
          title: '自定义中心',
          children: [{ key: 'custom-entry', title: '入口页', path: '/custom/entry' }],
        },
      ],
    })

    const navigationStore = useNavigationStore()

    expect(navigationStore.defaultPath).toBe('/custom/entry')
    expect(navigationStore.resolveBreadcrumb('/custom/entry')).toEqual(['自定义中心', '入口页'])
  })

  it('keeps compute detail routes under commercial software breadcrumb', () => {
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

    expect(navigationStore.resolveBreadcrumb('/compute/pools/10')).toEqual(['计算资源', '应用详情'])
  })
})
