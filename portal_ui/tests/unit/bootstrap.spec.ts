import { createMemoryHistory } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as computeApi from '@/services/api/compute'
import * as sessionApi from '@/services/api/session'
import { bootstrapPortalApp, createPortalApp } from '@/bootstrap'
import { createPortalRouter } from '@/router'

describe('portal app bootstrap', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
    vi.spyOn(computeApi, 'listRemoteApps').mockResolvedValue({
      data: [],
      headers: {},
    } as never)
  })

  it('mounts the shell with router and Pinia installed', async () => {
    const router = createPortalRouter(createMemoryHistory())
    router.push('/compute/commercial')
    await router.isReady()

    const host = document.createElement('div')

    expect(() => createPortalApp(router).mount(host)).not.toThrow()
    expect(host.textContent).toContain('可用软件列表')
  })

  it('lets the router guard redirect root route from navigation store default path', async () => {
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
        capabilities: ['compute.view'],
        menu_tree: [
          {
            key: 'compute',
            title: '计算资源',
            children: [{ key: 'compute-tools', title: '计算工具', path: '/compute/tools' }],
          },
        ],
        org_context: {},
      },
      headers: {},
    } as never)

    const router = createPortalRouter(createMemoryHistory())
    const replaceSpy = vi.spyOn(router, 'replace')

    const result = await bootstrapPortalApp(router)
    expect(result).not.toBeNull()
    if (!result) {
      throw new Error('bootstrapPortalApp unexpectedly returned null for authenticated session')
    }
    const host = document.createElement('div')
    result.app.mount(host)
    await router.isReady()

    expect(replaceSpy).not.toHaveBeenCalled()
    expect(router.currentRoute.value.path).toBe('/compute/tools')
    expect(host.textContent).toContain('计算工具列表')
  })

  it('keeps the current route when bootstrap provides no default entry', async () => {
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
        capabilities: ['compute.view'],
        menu_tree: [],
        org_context: {},
      },
      headers: {},
    } as never)

    const router = createPortalRouter(createMemoryHistory())
    const result = await bootstrapPortalApp(router)

    expect(result).not.toBeNull()
    if (!result) {
      throw new Error('bootstrapPortalApp unexpectedly returned null for authenticated session')
    }
    const host = document.createElement('div')
    result.app.mount(host)
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/')
  })

  it('redirects to login when session bootstrap returns anonymous context', async () => {
    const redirectToLogin = vi.fn()
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

    const router = createPortalRouter(createMemoryHistory())
    router.push('/')
    await router.isReady()

    const result = await bootstrapPortalApp(router, redirectToLogin)

    expect(result).toBeNull()
    expect(redirectToLogin).toHaveBeenCalledTimes(1)
    expect(router.currentRoute.value.path).toBe('/')
  })

  it('redirects to login when session bootstrap fails', async () => {
    const redirectToLogin = vi.fn()
    vi.spyOn(sessionApi, 'getSessionBootstrap').mockRejectedValue(new Error('offline'))

    const router = createPortalRouter(createMemoryHistory())
    router.push('/')
    await router.isReady()

    const result = await bootstrapPortalApp(router, redirectToLogin)

    expect(result).toBeNull()
    expect(redirectToLogin).toHaveBeenCalledTimes(1)
  })
})
