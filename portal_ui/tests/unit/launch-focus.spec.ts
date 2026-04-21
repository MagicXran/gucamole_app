import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/http', () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
  },
}))

const http = (await import('@/services/http')).default

describe('launchRemoteApp popup focus handling', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('renders the Guacamole iframe with Chromium-safe focus handoff', async () => {
    vi.mocked(http.post).mockResolvedValue({
      data: {
        status: 'started',
        redirect_url: 'http://127.0.0.1:8880/guacamole/#/client/app-token',
        connection_name: 'app_1',
        session_id: 'session-1',
        queue_id: 0,
        position: 0,
        pool_id: 1,
      },
      headers: {},
    } as never)

    let html = ''
    const popup = {
      closed: false,
      document: {
        open: vi.fn(),
        write: vi.fn((value: string) => {
          html += value
        }),
        close: vi.fn(),
      },
    } as unknown as Window
    vi.spyOn(window, 'open').mockReturnValue(popup)

    const { launchRemoteApp } = await import('@/modules/compute/services/launch')
    await launchRemoteApp(1, '记事本', 1)

    expect(html).toContain('id="guac-frame"')
    expect(html).toContain('tabindex="-1"')
    expect(html).toContain('focusGuacamoleFrame')
    expect(html).toContain('contentWindow.focus')
    expect(html).toContain('frame.addEventListener("load",focusGuacamoleFrame)')
    expect(html).toContain('window.addEventListener("focus",focusGuacamoleFrame)')
    expect(html).toContain('document.addEventListener("click",focusGuacamoleFrame,true)')
  })
})
