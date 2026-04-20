import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as computeApi from '@/services/api/compute'
import SimulationAppView from '@/modules/compute/views/SimulationAppView.vue'
import { useComputeStore } from '@/stores/compute'

describe('SimulationAppView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('only renders simulation_app resources', () => {
    const store = useComputeStore()
    store.apps = [
      {
        id: 1,
        pool_id: 10,
        app_kind: 'simulation_app',
        name: '仿真脚本平台',
        icon: 'terminal',
        protocol: 'rdp',
        supports_gui: true,
        supports_script: true,
        script_runtime_id: 1,
        script_profile_key: 'solver',
        script_profile_name: 'Solver',
        script_schedulable: true,
        script_status_code: 'ready',
        script_status_label: '可调度',
        script_status_tone: 'success',
        script_status_summary: '',
        script_status_reason: '',
        resource_status_code: 'available',
        resource_status_label: '可用',
        resource_status_tone: 'success',
        active_count: 0,
        queued_count: 0,
        max_concurrent: 1,
        has_capacity: true,
      },
      {
        id: 2,
        pool_id: 11,
        app_kind: 'compute_tool',
        name: '热力学计算器',
        icon: 'calculate',
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
        resource_status_code: 'available',
        resource_status_label: '可用',
        resource_status_tone: 'success',
        active_count: 0,
        queued_count: 0,
        max_concurrent: 1,
        has_capacity: true,
      },
    ] as never
    store.loaded = true

    const wrapper = mount(SimulationAppView, {
      global: {
        stubs: {
          RouterLink: { template: '<a><slot /></a>' },
        },
      },
    })

    expect(wrapper.text()).toContain('仿真脚本平台')
    expect(wrapper.text()).not.toContain('热力学计算器')
  })

  it('loads data on mount when store is empty', async () => {
    vi.spyOn(computeApi, 'listRemoteApps').mockResolvedValue({
      data: [
        {
          id: 1,
          pool_id: 10,
          app_kind: 'simulation_app',
          name: '仿真脚本平台',
          icon: 'terminal',
          protocol: 'rdp',
          supports_gui: true,
          supports_script: true,
          script_runtime_id: 1,
          script_profile_key: 'solver',
          script_profile_name: 'Solver',
          script_schedulable: true,
          script_status_code: 'ready',
          script_status_label: '可调度',
          script_status_tone: 'success',
          script_status_summary: '',
          script_status_reason: '',
          resource_status_code: 'available',
          resource_status_label: '可用',
          resource_status_tone: 'success',
          active_count: 0,
          queued_count: 0,
          max_concurrent: 1,
          has_capacity: true,
        },
      ],
      headers: {},
    } as never)

    const wrapper = mount(SimulationAppView, {
      global: {
        stubs: {
          RouterLink: { template: '<a><slot /></a>' },
        },
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('仿真脚本平台')
  })

  it('shows loading state before data resolves', () => {
    const store = useComputeStore()
    store.loading = true
    store.loaded = false
    const listSpy = vi.spyOn(computeApi, 'listRemoteApps').mockResolvedValue({ data: [], headers: {} } as never)

    const wrapper = mount(SimulationAppView)

    expect(wrapper.text()).toContain('加载中')
    expect(wrapper.text()).not.toContain('暂无仿真应用')
    expect(listSpy).not.toHaveBeenCalled()
  })

  it('shows error state instead of empty state', () => {
    const store = useComputeStore()
    store.errorMessage = '接口炸了'
    store.loaded = true
    const listSpy = vi.spyOn(computeApi, 'listRemoteApps').mockResolvedValue({ data: [], headers: {} } as never)

    const wrapper = mount(SimulationAppView)

    expect(wrapper.text()).toContain('接口炸了')
    expect(wrapper.text()).not.toContain('暂无仿真应用')
    expect(listSpy).not.toHaveBeenCalled()
  })
})
