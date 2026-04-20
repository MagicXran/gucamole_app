import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { PORTAL_TOKEN_KEY } from '@/constants/auth'
import * as sessionApi from '@/services/api/session'
import { useSessionStore } from '@/stores/session'

describe('session store bootstrap', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('hydrates authenticated user context from backend bootstrap', async () => {
    localStorage.setItem(PORTAL_TOKEN_KEY, 'token-a')
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
            children: [
              {
                key: 'compute-commercial',
                title: '商业软件',
                path: '/compute/commercial',
              },
            ],
          },
        ],
        org_context: { department: '研发' },
      },
      headers: {},
    } as never)

    const store = useSessionStore()
    await store.bootstrap()

    expect(store.authenticated).toBe(true)
    expect(store.authSource).toBe('local')
    expect(store.user?.username).toBe('alice')
    expect(store.capabilities).toContain('ops.app.view')
    expect(store.menuTree[0].key).toBe('compute')
    expect(store.orgContext).toEqual({ department: '研发' })
    expect(store.bootstrapLoaded).toBe(true)
    expect(localStorage.getItem('portal_user')).toBe(
      JSON.stringify({
        user_id: 7,
        username: 'alice',
        display_name: 'Alice',
        is_admin: false,
      }),
    )
  })

  it('clears legacy portal token when bootstrap returns anonymous session', async () => {
    localStorage.setItem(PORTAL_TOKEN_KEY, 'stale-token')
    localStorage.setItem(
      'portal_user',
      JSON.stringify({
        user_id: 9,
        username: 'legacy',
        display_name: 'Legacy User',
        is_admin: false,
      }),
    )
    vi.spyOn(sessionApi, 'getSessionBootstrap').mockResolvedValue({
      data: {
        authenticated: false,
        auth_source: 'anonymous',
        user: null,
        capabilities: [],
        menu_tree: [],
        org_context: {},
      },
      headers: {},
    } as never)

    const store = useSessionStore()
    await store.bootstrap()

    expect(store.authenticated).toBe(false)
    expect(store.authSource).toBe('anonymous')
    expect(store.user).toBeNull()
    expect(localStorage.getItem(PORTAL_TOKEN_KEY)).toBeNull()
    expect(localStorage.getItem('portal_user')).toBeNull()
  })
})
