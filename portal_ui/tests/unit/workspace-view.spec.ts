import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { defineComponent } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import WorkspaceView from '@/modules/my/views/WorkspaceView.vue'
import type { WorkspaceFileItem } from '@/modules/my/types/files'

const apiMocks = vi.hoisted(() => ({
  getSpaceInfo: vi.fn(),
  listFiles: vi.fn(),
  createDirectory: vi.fn(),
  deleteFile: vi.fn(),
  requestDownloadToken: vi.fn(),
  moveFile: vi.fn(),
  uploadInit: vi.fn(),
  uploadChunk: vi.fn(),
  cancelUpload: vi.fn(),
}))

vi.mock('@/modules/my/services/api/files', () => apiMocks)

const FileBrowserStub = defineComponent({
  name: 'FileBrowser',
  props: {
    currentPath: { type: String, default: '' },
    items: { type: Array, default: () => [] },
    loading: { type: Boolean, default: false },
    errorMessage: { type: String, default: '' },
  },
  emits: [
    'refresh',
    'navigate',
    'create-directory',
    'delete-entry',
    'download-entry',
    'view-entry',
    'move-entry',
    'upload-files',
    'open-directory',
  ],
  setup(_, { emit }) {
    const uploadFile = {
      name: 'upload.txt',
      size: 7,
      slice: (start: number, end: number) => new Blob(['payload'].slice(start, end)),
    } as File

    return {
      emitUpload: () => emit('upload-files', [uploadFile]),
    }
  },
  template: `
    <div>
      <div data-testid="browser-path">{{ currentPath }}</div>
      <div data-testid="browser-count">{{ items.length }}</div>
      <div data-testid="browser-error">{{ errorMessage }}</div>
      <button data-testid="refresh" @click="$emit('refresh')" />
      <button data-testid="mkdir" @click="$emit('create-directory', 'reports')" />
      <button
        data-testid="delete"
        @click="$emit('delete-entry', { name: 'obsolete.txt', is_dir: false, size: 10, mtime: 1 })"
      />
      <button
        data-testid="download"
        @click="$emit('download-entry', { name: 'report.txt', is_dir: false, size: 12, mtime: 1 })"
      />
      <button
        data-testid="view"
        @click="$emit('view-entry', { name: 'mesh.vtu', is_dir: false, size: 24, mtime: 1 })"
      />
      <button
        data-testid="move"
        @click="$emit('move-entry', { sourcePath: 'report.txt', targetPath: 'archive/report.txt' })"
      />
      <button
        data-testid="upload"
        @click="emitUpload"
      />
      <button data-testid="navigate" @click="$emit('navigate', 'nested/output')" />
      <button
        data-testid="open"
        @click="$emit('open-directory', { name: 'cases', is_dir: true, size: 0, mtime: 1 })"
      />
    </div>
  `,
})

function buildListResponse(path = 'workspace', items: WorkspaceFileItem[] = []) {
  return Promise.resolve({
    data: {
      path,
      items,
    },
    headers: {},
  } as never)
}

function buildRouter(initialPath = '/my/workspace?path=workspace') {
  return createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/my/workspace', component: WorkspaceView }],
  })
}

describe('WorkspaceView', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    apiMocks.getSpaceInfo.mockResolvedValue({
      data: {
        used_bytes: 1024,
        quota_bytes: 4096,
        used_display: '1 KB',
        quota_display: '4 KB',
        usage_percent: 25,
      },
      headers: {},
    } as never)
    apiMocks.listFiles.mockImplementation((path?: string) =>
      buildListResponse(path ?? '', [
        { name: 'cases', is_dir: true, size: 0, mtime: 1710000000 },
        { name: 'report.txt', is_dir: false, size: 512, mtime: 1710000001 },
      ]),
    )
    apiMocks.createDirectory.mockResolvedValue({ data: { message: '已创建' }, headers: {} } as never)
    apiMocks.deleteFile.mockResolvedValue({ data: { message: '已删除' }, headers: {} } as never)
    apiMocks.requestDownloadToken.mockResolvedValue({
      data: { token: 'download-token', expires_in: 300 },
      headers: {},
    } as never)
    apiMocks.moveFile.mockResolvedValue({ data: { message: '已移动' }, headers: {} } as never)
    apiMocks.uploadInit.mockResolvedValue({
      data: { upload_id: 'upload-a', offset: 0, chunk_size: 4 },
      headers: {},
    } as never)
    apiMocks.uploadChunk
      .mockResolvedValueOnce({
        data: { offset: 4, complete: false },
        headers: {},
      } as never)
      .mockResolvedValueOnce({
        data: { offset: 7, complete: true },
        headers: {},
      } as never)
    apiMocks.cancelUpload.mockResolvedValue({ data: { message: '已取消' }, headers: {} } as never)
    vi.stubGlobal('open', vi.fn())
  })

  it('loads quota and deep-linked path on mount', async () => {
    const router = buildRouter()
    await router.push('/my/workspace?path=workspace/output')
    await router.isReady()

    const wrapper = mount(WorkspaceView, {
      global: {
        plugins: [createPinia(), router],
        stubs: {
          FileBrowser: FileBrowserStub,
        },
      },
    })
    await flushPromises()

    expect(apiMocks.getSpaceInfo).toHaveBeenCalledTimes(1)
    expect(apiMocks.listFiles).toHaveBeenCalledWith('workspace/output')
    expect(wrapper.text()).toContain('个人空间')
    expect(wrapper.text()).toContain('1 KB')
    expect(wrapper.text()).toContain('4 KB')
    expect(wrapper.get('[data-testid="browser-path"]').text()).toBe('workspace/output')
    expect(wrapper.get('[data-testid="browser-count"]').text()).toBe('2')
  })

  it('keeps the directory usable when quota loading fails', async () => {
    apiMocks.getSpaceInfo.mockRejectedValueOnce(new Error('配额接口失败'))
    const router = buildRouter()
    await router.push('/my/workspace?path=workspace/output')
    await router.isReady()

    const wrapper = mount(WorkspaceView, {
      global: {
        plugins: [createPinia(), router],
        stubs: {
          FileBrowser: FileBrowserStub,
        },
      },
    })
    await flushPromises()

    expect(apiMocks.listFiles).toHaveBeenCalledWith('workspace/output')
    expect(wrapper.get('[data-testid="browser-path"]').text()).toBe('workspace/output')
    expect(wrapper.get('[data-testid="browser-count"]').text()).toBe('2')
    expect(wrapper.text()).toContain('个人空间')
  })

  it('handles create, delete, move, download, upload, and navigation actions', async () => {
    const router = buildRouter()
    await router.push('/my/workspace?path=workspace')
    await router.isReady()

    const wrapper = mount(WorkspaceView, {
      global: {
        plugins: [createPinia(), router],
        stubs: {
          FileBrowser: FileBrowserStub,
        },
      },
    })
    await flushPromises()

    await wrapper.get('[data-testid="mkdir"]').trigger('click')
    await flushPromises()
    expect(apiMocks.createDirectory).toHaveBeenCalledWith('workspace/reports')

    await wrapper.get('[data-testid="delete"]').trigger('click')
    await flushPromises()
    expect(apiMocks.deleteFile).toHaveBeenCalledWith('workspace/obsolete.txt')

    await wrapper.get('[data-testid="move"]').trigger('click')
    await flushPromises()
    expect(apiMocks.moveFile).toHaveBeenCalledWith('workspace/report.txt', 'archive/report.txt')

    await wrapper.get('[data-testid="download"]').trigger('click')
    expect(apiMocks.requestDownloadToken).toHaveBeenCalledWith('workspace/report.txt')
    expect(window.open).toHaveBeenCalledWith('/api/files/download?_token=download-token', '_blank', 'noopener')

    await wrapper.get('[data-testid="view"]').trigger('click')
    expect(window.open).toHaveBeenCalledWith('/viewer.html?path=workspace%2Fmesh.vtu', '_blank', 'noopener')

    await wrapper.get('[data-testid="upload"]').trigger('click')
    await flushPromises()
    expect(apiMocks.uploadInit).toHaveBeenCalledWith('workspace/upload.txt', 7)
    expect(apiMocks.uploadChunk).toHaveBeenCalledTimes(2)

    await wrapper.get('[data-testid="navigate"]').trigger('click')
    await flushPromises()
    expect(apiMocks.listFiles).toHaveBeenLastCalledWith('nested/output')
    expect(router.currentRoute.value.query.path).toBe('nested/output')

    await wrapper.get('[data-testid="open"]').trigger('click')
    await flushPromises()
    expect(apiMocks.listFiles).toHaveBeenLastCalledWith('nested/output/cases')
    expect(router.currentRoute.value.query.path).toBe('nested/output/cases')
  })

  it('shows operation errors instead of dropping rejected actions into the console', async () => {
    apiMocks.createDirectory.mockRejectedValueOnce(new Error('文件夹已存在'))
    const router = buildRouter()
    await router.push('/my/workspace?path=workspace')
    await router.isReady()

    const wrapper = mount(WorkspaceView, {
      global: {
        plugins: [createPinia(), router],
        stubs: {
          FileBrowser: FileBrowserStub,
        },
      },
    })
    await flushPromises()

    await wrapper.get('[data-testid="mkdir"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('文件夹已存在')
  })
})
