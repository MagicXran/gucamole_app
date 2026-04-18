import { afterEach, describe, expect, it, vi } from 'vitest'

describe('http transport', () => {
  afterEach(() => {
    vi.resetModules()
    localStorage.clear()
  })

  it('adds bearer token to outgoing requests', async () => {
    localStorage.setItem('portal_token', 'old-token')

    const { default: http } = await import('@/services/http')
    const requestHandler = (http.interceptors.request as any).handlers[0].fulfilled

    const config = await requestHandler({ headers: {} })

    expect(config.headers.Authorization).toBe('Bearer old-token')
  })

  it('rotates portal token from refresh-token response header', async () => {
    localStorage.setItem('portal_token', 'old-token')

    const { default: http } = await import('@/services/http')
    const responseHandler = (http.interceptors.response as any).handlers[0].fulfilled

    await responseHandler({
      headers: {
        'refresh-token': 'new-token',
      },
      data: {},
    })

    expect(localStorage.getItem('portal_token')).toBe('new-token')
  })
})
