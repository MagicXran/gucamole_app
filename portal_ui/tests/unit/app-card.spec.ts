import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import AppCard from '@/modules/compute/components/AppCard.vue'
import { launchRemoteApp } from '@/modules/compute/services/launch'

vi.mock('@/modules/compute/services/launch', () => ({
  launchRemoteApp: vi.fn(),
}))

const APP = {
  id: 4,
  pool_id: 4,
  name: '验证池-桌面与脚本',
  icon: 'desktop',
  protocol: 'rdp',
  supports_gui: true,
  supports_script: true,
  script_runtime_id: 4,
  script_profile_key: null,
  script_profile_name: null,
  script_schedulable: false,
  script_status_code: 'no_active_workers',
  script_status_label: '无活跃节点',
  script_status_tone: 'warn',
  script_status_summary: '0/0 活跃节点满足 脚本任务',
  script_status_reason: '当前节点组没有活跃 Worker 节点',
  resource_status_code: 'available',
  resource_status_label: '可用',
  resource_status_tone: 'success',
  active_count: 0,
  queued_count: 0,
  max_concurrent: 1,
  has_capacity: true,
} as const

describe('AppCard', () => {
  beforeEach(() => {
    vi.mocked(launchRemoteApp).mockReset()
    vi.mocked(launchRemoteApp).mockResolvedValue(undefined)
  })

  it('launches remote app when clicking the card body', async () => {
    const wrapper = mount(AppCard, {
      props: { app: APP },
      global: {
        stubs: {
          RouterLink: {
            template: '<a class="detail-link"><slot /></a>',
          },
        },
      },
    })

    await wrapper.get('.app-card').trigger('click')

    expect(launchRemoteApp).toHaveBeenCalledWith(APP.id, APP.name, APP.pool_id)
  })

  it('does not launch when clicking the detail link', async () => {
    const wrapper = mount(AppCard, {
      props: { app: APP },
      global: {
        stubs: {
          RouterLink: {
            template: '<a class="detail-link"><slot /></a>',
          },
        },
      },
    })

    await wrapper.get('.detail-link').trigger('click')

    expect(launchRemoteApp).not.toHaveBeenCalled()
  })

  it('shows launch errors inline', async () => {
    vi.mocked(launchRemoteApp).mockRejectedValue(new Error('远程应用启动失败'))
    const wrapper = mount(AppCard, {
      props: { app: APP },
      global: {
        stubs: {
          RouterLink: {
            template: '<a class="detail-link"><slot /></a>',
          },
        },
      },
    })

    await wrapper.get('.app-card').trigger('click')
    await Promise.resolve()

    expect(wrapper.text()).toContain('远程应用启动失败')
  })
})
