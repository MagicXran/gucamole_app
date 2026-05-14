import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import FileBrowser from '@/modules/my/components/FileBrowser.vue'
import type { WorkspaceFileItem } from '@/modules/my/types/files'

function file(name: string): WorkspaceFileItem {
  return { name, is_dir: false, size: 128, mtime: 1710000000 }
}

function directory(name: string): WorkspaceFileItem {
  return { name, is_dir: true, size: 0, mtime: 1710000000 }
}

describe('FileBrowser move dialog', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders items and emits navigation plus row actions', async () => {
    const promptSpy = vi.spyOn(window, 'prompt')
    const confirmSpy = vi.spyOn(window, 'confirm')
    promptSpy.mockReturnValueOnce('new-folder')
    confirmSpy.mockReturnValue(true)

    const wrapper = mount(FileBrowser, {
      props: {
        currentPath: 'workspace/output',
        loading: false,
        errorMessage: '',
        items: [
          { name: 'cases', is_dir: true, size: 0, mtime: 1710000000 },
          { name: 'mesh.vtu', is_dir: false, size: 1024, mtime: 1710000000 },
          { name: 'readme.txt', is_dir: false, size: 256, mtime: 1710000001 },
        ],
        directoryLoader: async () => [],
      },
    })

    expect(wrapper.text()).toContain('workspace')
    expect(wrapper.text()).toContain('output')
    expect(wrapper.text()).toContain('cases')
    expect(wrapper.text()).toContain('mesh.vtu')
    expect(wrapper.text()).toContain('readme.txt')

    await wrapper.get('[data-testid="breadcrumb-workspace"]').trigger('click')
    await wrapper.get('[data-testid="entry-open-cases"]').trigger('click')
    await wrapper.get('[data-testid="mkdir-button"]').trigger('click')
    await wrapper.get('[data-testid="view-mesh.vtu"]').trigger('click')
    await wrapper.get('[data-testid="download-readme.txt"]').trigger('click')
    await wrapper.get('[data-testid="delete-readme.txt"]').trigger('click')

    expect(wrapper.emitted('navigate')?.[0]).toEqual(['workspace'])
    expect(wrapper.emitted('open-directory')?.[0]?.[0]).toMatchObject({ name: 'cases', is_dir: true })
    expect(wrapper.emitted('create-directory')?.[0]).toEqual(['new-folder'])
    expect(wrapper.emitted('view-entry')?.[0]?.[0]).toMatchObject({ name: 'mesh.vtu', is_dir: false })
    expect(wrapper.emitted('download-entry')?.[0]?.[0]).toMatchObject({ name: 'readme.txt', is_dir: false })
    expect(wrapper.emitted('delete-entry')?.[0]?.[0]).toMatchObject({ name: 'readme.txt', is_dir: false })
  })

  it('emits selected files from the upload input', async () => {
    const wrapper = mount(FileBrowser, {
      props: {
        currentPath: '',
        loading: false,
        errorMessage: '',
        items: [],
        directoryLoader: async () => [],
      },
    })

    const input = wrapper.get('input[type="file"]')
    const uploadFile = new File(['abc'], 'demo.txt', { type: 'text/plain' })
    Object.defineProperty(input.element, 'files', {
      value: [uploadFile],
      configurable: true,
    })

    await input.trigger('change')

    const emittedFiles = wrapper.emitted('upload-files')?.[0]?.[0] as File[]

    expect(emittedFiles).toHaveLength(1)
    expect(emittedFiles[0]?.name).toBe('demo.txt')
  })

  it('opens a directory picker instead of using the browser prompt', async () => {
    const promptSpy = vi.spyOn(window, 'prompt')
    const directoryLoader = vi.fn(async (path: string) => {
      if (path === '') {
        return [directory('111'), directory('Archive')]
      }
      return []
    })

    const wrapper = mount(FileBrowser, {
      props: {
        currentPath: '111',
        items: [file('debian.iso')],
        loading: false,
        errorMessage: '',
        directoryLoader,
      },
    })

    await wrapper.get('[data-testid="move-debian.iso"]').trigger('click')
    await flushPromises()

    expect(promptSpy).not.toHaveBeenCalled()
    expect(wrapper.get('[data-testid="move-dialog"]').text()).toContain('移动 debian.iso')
    expect(directoryLoader).toHaveBeenCalledWith('')
  })

  it('blocks moving an entry into its current directory', async () => {
    const wrapper = mount(FileBrowser, {
      props: {
        currentPath: '111',
        items: [file('debian.iso')],
        loading: false,
        errorMessage: '',
        directoryLoader: async () => [directory('111'), directory('Archive')],
      },
    })

    await wrapper.get('[data-testid="move-debian.iso"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="move-target-111"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="move-error"]').text()).toContain('文件已在当前目录中')
    expect(wrapper.get<HTMLButtonElement>('[data-testid="move-confirm"]').element.disabled).toBe(true)
    expect(wrapper.emitted('move-entry')).toBeUndefined()
  })

  it('blocks moving when the target directory already contains the same name', async () => {
    const directoryLoader = vi.fn(async (path: string) => {
      if (path === '') {
        return [directory('Archive')]
      }
      if (path === 'Archive') {
        return [file('debian.iso')]
      }
      return []
    })

    const wrapper = mount(FileBrowser, {
      props: {
        currentPath: '111',
        items: [file('debian.iso')],
        loading: false,
        errorMessage: '',
        directoryLoader,
      },
    })

    await wrapper.get('[data-testid="move-debian.iso"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="move-target-Archive"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="move-error"]').text()).toContain('目标目录已存在同名文件或文件夹')
    expect(wrapper.get<HTMLButtonElement>('[data-testid="move-confirm"]').element.disabled).toBe(true)
    expect(wrapper.emitted('move-entry')).toBeUndefined()
  })

  it('emits a move payload for a valid selected directory', async () => {
    const directoryLoader = vi.fn(async (path: string) => {
      if (path === '') {
        return [directory('Archive')]
      }
      return []
    })

    const wrapper = mount(FileBrowser, {
      props: {
        currentPath: '111',
        items: [file('debian.iso')],
        loading: false,
        errorMessage: '',
        directoryLoader,
      },
    })

    await wrapper.get('[data-testid="move-debian.iso"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="move-target-Archive"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="move-confirm"]').trigger('click')

    expect(wrapper.emitted('move-entry')).toEqual([
      [
        {
          sourcePath: '111/debian.iso',
          targetPath: 'Archive/debian.iso',
        },
      ],
    ])
  })
})
