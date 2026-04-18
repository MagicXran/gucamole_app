import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory } from 'vue-router'

import { createPortalRouter } from '@/router'
import * as sdkApi from '@/modules/sdk/services/api/sdk'
import { useNavigationStore } from '@/stores/navigation'
import { useSessionStore } from '@/stores/session'

const menuTree = [
  {
    key: 'compute',
    title: '计算资源',
    children: [{ key: 'compute-commercial', title: '商业软件', path: '/compute/commercial' }],
  },
  {
    key: 'sdk',
    title: 'SDK中心',
    children: [
      { key: 'sdk-cloud', title: '云平台SDK', path: '/sdk/cloud' },
      { key: 'sdk-simulation-app', title: '仿真AppSDK', path: '/sdk/simulation-app' },
    ],
  },
]

const packages = [
  {
    id: 1,
    package_kind: 'cloud_platform',
    name: '云平台 Python SDK',
    summary: '调用云平台 API',
    homepage_url: 'https://example.test/cloud',
  },
  {
    id: 2,
    package_kind: 'simulation_app',
    name: '仿真 App SDK',
    summary: '构建仿真 App',
    homepage_url: 'https://example.test/sim',
  },
]

const details = {
  1: {
    ...packages[0],
    versions: [
      {
        id: 11,
        package_id: 1,
        version: '1.2.0',
        release_notes: '新增任务查询',
        released_at: '2026-04-17 09:00:00',
        assets: [
          {
            id: 101,
            version_id: 11,
            asset_kind: 'wheel',
            display_name: 'cloud-sdk-1.2.0.whl',
            download_url: 'https://downloads.example.test/cloud-sdk-1.2.0.whl',
            size_bytes: 4096,
            sort_order: 10,
          },
        ],
      },
    ],
  },
  2: {
    ...packages[1],
    versions: [
      {
        id: 21,
        package_id: 2,
        version: '0.9.0',
        release_notes: 'App 模板',
        released_at: '2026-04-16 09:00:00',
        assets: [
          {
            id: 201,
            version_id: 21,
            asset_kind: 'zip',
            display_name: 'simulation-app-sdk.zip',
            download_url: 'https://downloads.example.test/simulation-app-sdk.zip',
            size_bytes: 8192,
            sort_order: 10,
          },
        ],
      },
    ],
  },
}

function createDeferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((innerResolve, innerReject) => {
    resolve = innerResolve
    reject = innerReject
  })
  return { promise, resolve, reject }
}

describe('SDK center Vue pages', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()

    const sessionStore = useSessionStore()
    sessionStore.$patch({
      authenticated: true,
      menuTree,
    })

    vi.spyOn(sdkApi, 'getSdkPackages').mockImplementation(async (packageKind) => ({
      data: packages.filter((item) => item.package_kind === packageKind),
      headers: {},
    }) as never)
    vi.spyOn(sdkApi, 'getSdkPackageDetail').mockImplementation(async (packageId) => ({
      data: details[packageId as keyof typeof details],
      headers: {},
    }) as never)
  })

  it('registers SDK routes and resolves SDK breadcrumbs without changing compute default', async () => {
    const router = createPortalRouter(createMemoryHistory())
    const navigationStore = useNavigationStore()

    expect(navigationStore.defaultPath).toBe('/compute/commercial')
    expect(navigationStore.resolveBreadcrumb('/sdk/cloud')).toEqual(['SDK中心', '云平台SDK'])
    expect(navigationStore.resolveBreadcrumb('/sdk/simulation-app')).toEqual(['SDK中心', '仿真AppSDK'])

    await router.push('/sdk/cloud')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/sdk/cloud')

    await router.push('/sdk/simulation-app')
    expect(router.currentRoute.value.path).toBe('/sdk/simulation-app')
  })

  it('loads only cloud platform packages, supports search, shows versions, and downloads real assets', async () => {
    const openedWindow = { location: { href: '' }, opener: {} as unknown }
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => openedWindow as Window)
    vi.spyOn(sdkApi, 'createSdkAssetDownloadToken').mockResolvedValue({
      data: { token: 'sdk-token-101', expires_in: 300 },
      headers: {},
    } as never)
    const router = createPortalRouter(createMemoryHistory())
    await router.push('/sdk/cloud')
    await router.isReady()

    const { default: CloudSdkView } = await import('@/modules/sdk/views/CloudSdkView.vue')
    const wrapper = mount(CloudSdkView, {
      global: {
        plugins: [router],
      },
    })
    await flushPromises()

    expect(sdkApi.getSdkPackages).toHaveBeenCalledWith('cloud_platform')
    expect(sdkApi.getSdkPackageDetail).toHaveBeenCalledWith(1)
    expect(wrapper.text()).toContain('云平台 Python SDK')
    expect(wrapper.text()).not.toContain('仿真 App SDK')

    await wrapper.get('input[type="search"]').setValue('python')
    expect(wrapper.text()).toContain('云平台 Python SDK')

    expect(wrapper.text()).toContain('1.2.0')
    expect(wrapper.text()).toContain('新增任务查询')
    expect(wrapper.text()).toContain('cloud-sdk-1.2.0.whl')

    await wrapper.get('[data-testid="sdk-download-101"]').trigger('click')
    expect(openSpy).toHaveBeenCalledWith('', '_blank')
    await flushPromises()

    expect(sdkApi.createSdkAssetDownloadToken).toHaveBeenCalledWith(101)
    expect(openedWindow.opener).toBeNull()
    expect(openedWindow.location.href).toBe('/api/sdks/assets/101/download?_token=sdk-token-101')
  })

  it('loads only simulation app SDK packages with their versioned assets', async () => {
    const router = createPortalRouter(createMemoryHistory())
    await router.push('/sdk/simulation-app')
    await router.isReady()

    const { default: SimulationAppSdkView } = await import('@/modules/sdk/views/SimulationAppSdkView.vue')
    const wrapper = mount(SimulationAppSdkView, {
      global: {
        plugins: [router],
      },
    })
    await flushPromises()

    expect(sdkApi.getSdkPackages).toHaveBeenCalledWith('simulation_app')
    expect(sdkApi.getSdkPackageDetail).toHaveBeenCalledWith(2)
    expect(wrapper.text()).toContain('仿真 App SDK')
    expect(wrapper.text()).not.toContain('云平台 Python SDK')
    expect(wrapper.text()).toContain('0.9.0')
    expect(wrapper.text()).toContain('App 模板')
    expect(wrapper.text()).toContain('simulation-app-sdk.zip')
  })

  it('does not leak cloud search keyword into simulation page', async () => {
    const router = createPortalRouter(createMemoryHistory())
    await router.push('/sdk/cloud')
    await router.isReady()

    const { default: CloudSdkView } = await import('@/modules/sdk/views/CloudSdkView.vue')
    const { default: SimulationAppSdkView } = await import('@/modules/sdk/views/SimulationAppSdkView.vue')

    const cloudWrapper = mount(CloudSdkView, {
      global: {
        plugins: [router],
      },
    })
    await flushPromises()

    await cloudWrapper.get('input[type="search"]').setValue('python')
    expect(cloudWrapper.text()).toContain('云平台 Python SDK')

    await router.push('/sdk/simulation-app')
    await router.isReady()
    const simulationWrapper = mount(SimulationAppSdkView, {
      global: {
        plugins: [router],
      },
    })
    await flushPromises()

    expect((simulationWrapper.get('input[type="search"]').element as HTMLInputElement).value).toBe('')
    expect(simulationWrapper.text()).toContain('仿真 App SDK')
    expect(simulationWrapper.text()).not.toContain('暂无匹配 SDK')
  })

  it('ignores stale cloud responses after switching to simulation sdk page', async () => {
    const cloudDeferred = createDeferred<{ data: typeof packages; headers: Record<string, string> }>()
    const simulationDeferred = createDeferred<{ data: typeof packages; headers: Record<string, string> }>()

    vi.mocked(sdkApi.getSdkPackages).mockImplementation((packageKind) => {
      if (packageKind === 'cloud_platform') {
        return cloudDeferred.promise as never
      }
      return simulationDeferred.promise as never
    })

    const router = createPortalRouter(createMemoryHistory())
    await router.push('/sdk/cloud')
    await router.isReady()

    const { default: CloudSdkView } = await import('@/modules/sdk/views/CloudSdkView.vue')
    const { default: SimulationAppSdkView } = await import('@/modules/sdk/views/SimulationAppSdkView.vue')

    const cloudWrapper = mount(CloudSdkView, {
      global: {
        plugins: [router],
      },
    })

    await router.push('/sdk/simulation-app')
    await router.isReady()
    cloudWrapper.unmount()

    const simulationWrapper = mount(SimulationAppSdkView, {
      global: {
        plugins: [router],
      },
    })

    simulationDeferred.resolve({
      data: packages.filter((item) => item.package_kind === 'simulation_app'),
      headers: {},
    })
    await flushPromises()

    expect(simulationWrapper.text()).toContain('仿真 App SDK')
    expect(simulationWrapper.text()).not.toContain('云平台 Python SDK')

    cloudDeferred.resolve({
      data: packages.filter((item) => item.package_kind === 'cloud_platform'),
      headers: {},
    })
    await flushPromises()

    expect(simulationWrapper.text()).toContain('仿真 App SDK')
    expect(simulationWrapper.text()).not.toContain('云平台 Python SDK')
    expect(sdkApi.getSdkPackageDetail).toHaveBeenCalledWith(2)
    expect(sdkApi.getSdkPackageDetail).not.toHaveBeenCalledWith(1)
  })

  it('clears detail loading when a stale detail request is invalidated by switching sdk kind', async () => {
    const cloudDetailDeferred = createDeferred<{ data: (typeof details)[1]; headers: Record<string, string> }>()

    vi.mocked(sdkApi.getSdkPackages).mockImplementation(async (packageKind) => ({
      data: packageKind === 'cloud_platform'
        ? packages.filter((item) => item.package_kind === 'cloud_platform')
        : [],
      headers: {},
    }) as never)
    vi.mocked(sdkApi.getSdkPackageDetail).mockImplementation((packageId) => {
      if (packageId === 1) {
        return cloudDetailDeferred.promise as never
      }
      return Promise.resolve({
        data: details[packageId as keyof typeof details],
        headers: {},
      }) as never
    })

    const router = createPortalRouter(createMemoryHistory())
    await router.push('/sdk/cloud')
    await router.isReady()

    const { default: CloudSdkView } = await import('@/modules/sdk/views/CloudSdkView.vue')
    const { default: SimulationAppSdkView } = await import('@/modules/sdk/views/SimulationAppSdkView.vue')

    const cloudWrapper = mount(CloudSdkView, {
      global: {
        plugins: [router],
      },
    })
    await flushPromises()
    expect(cloudWrapper.text()).toContain('加载版本中...')

    await router.push('/sdk/simulation-app')
    await router.isReady()
    cloudWrapper.unmount()

    const simulationWrapper = mount(SimulationAppSdkView, {
      global: {
        plugins: [router],
      },
    })
    await flushPromises()

    expect(simulationWrapper.text()).not.toContain('加载版本中...')
    expect(simulationWrapper.text()).toContain('请选择 SDK 包查看版本。')
  })
})
