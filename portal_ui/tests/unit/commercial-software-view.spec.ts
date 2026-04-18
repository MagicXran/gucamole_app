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
        resource_status_code: 'queued',
        resource_status_label: '排队中',
        resource_status_tone: 'warning',
        active_count: 2,
        queued_count: 1,
        max_concurrent: 2,
        has_capacity: false,
      },
      {
        id: 3,
        pool_id: 12,
        name: '仿真脚本平台',
        icon: 'terminal',
        protocol: 'rdp',
        app_kind: 'simulation_app',
        supports_gui: true,
        supports_script: true,
        script_runtime_id: 3,
        script_profile_key: 'script',
        script_profile_name: 'Script',
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
    expect(wrapper.text()).toContain('排队中')
    expect(wrapper.text()).not.toContain('仿真脚本平台')
    expect(wrapper.findAll('.app-card__status')[1]?.text()).toBe('排队中')
    expect(wrapper.findAll('.app-card__status')[1]?.classes()).toContain('app-card__status--warning')

    await wrapper.find('input[type="search"]').setValue('comsol')

    expect(wrapper.text()).not.toContain('ANSYS Fluent')
    expect(wrapper.text()).toContain('COMSOL Multiphysics')
    expect(wrapper.text()).toContain('排队中')
    expect(wrapper.html()).toContain('/compute/pools/11')
  })
})
