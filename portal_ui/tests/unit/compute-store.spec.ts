import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

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
          active_count: 1,
          queued_count: 0,
          max_concurrent: 4,
          has_capacity: true,
        },
        {
          id: 2,
          pool_id: 20,
          name: 'COMSOL Multiphysics',
          icon: 'desktop',
          protocol: 'rdp',
          supports_gui: true,
          supports_script: true,
          script_runtime_id: 8,
          script_profile_key: 'comsol-batch',
          script_profile_name: 'COMSOL Batch',
          script_schedulable: true,
          script_status_code: 'ready',
          script_status_label: '可调度',
          script_status_tone: 'success',
          script_status_summary: '支持脚本运行',
          script_status_reason: '',
          resource_status_code: 'busy',
          resource_status_label: '繁忙',
          resource_status_tone: 'warning',
          active_count: 4,
          queued_count: 2,
          max_concurrent: 4,
          has_capacity: false,
        },
      ],
      headers: {},
    } as never)

    const store = useComputeStore()

    expect(store.loading).toBe(false)
    expect(store.errorMessage).toBe('')

    await store.loadApps()
    store.query = 'fluent'

    expect(store.loading).toBe(false)
    expect(store.errorMessage).toBe('')
    expect(store.apps).toHaveLength(2)
    expect(store.filteredApps.map((app) => app.name)).toEqual(['ANSYS Fluent'])
    expect(store.getAppByPoolId(20)?.name).toBe('COMSOL Multiphysics')
    expect(Object.prototype.hasOwnProperty.call(store, 'getAppById')).toBe(false)
    expect(store.loaded).toBe(true)
  })

  it('captures request failure sanely', async () => {
    vi.spyOn(computeApi, 'listRemoteApps').mockRejectedValue(new Error('boom'))

    const store = useComputeStore()
    await store.loadApps()

    expect(store.loading).toBe(false)
    expect(store.apps).toEqual([])
    expect(store.filteredApps).toEqual([])
    expect(store.errorMessage).toBe('boom')
    expect(store.getAppByPoolId(999)).toBeUndefined()
    expect(store.loaded).toBe(true)
  })

  it('keeps existing cards during background refresh failure', async () => {
    vi.spyOn(computeApi, 'listRemoteApps').mockRejectedValue(new Error('boom'))

    const store = useComputeStore()
    store.apps = [
      {
        id: 1,
        pool_id: 10,
        name: 'ANSYS Fluent',
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
        resource_status_code: 'available',
        resource_status_label: '可用',
        resource_status_tone: 'success',
        active_count: 1,
        queued_count: 0,
        max_concurrent: 4,
        has_capacity: true,
      },
    ] as never
    store.loaded = true

    const request = store.refreshApps()

    expect(store.loading).toBe(false)
    expect(store.refreshing).toBe(true)
    expect(store.apps).toHaveLength(1)

    await request

    expect(store.loading).toBe(false)
    expect(store.refreshing).toBe(false)
    expect(store.apps.map((app) => app.name)).toEqual(['ANSYS Fluent'])
    expect(store.errorMessage).toBe('')
    expect(store.refreshErrorMessage).toBe('boom')
  })
})
