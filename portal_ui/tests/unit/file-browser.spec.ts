import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import FileBrowser from '@/modules/my/components/FileBrowser.vue'

describe('FileBrowser', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders items and emits navigation plus row actions', async () => {
    const promptSpy = vi.spyOn(window, 'prompt')
    const confirmSpy = vi.spyOn(window, 'confirm')
    promptSpy
      .mockReturnValueOnce('new-folder')
      .mockReturnValueOnce('archive/readme.txt')
    confirmSpy.mockReturnValue(true)

    const wrapper = mount(FileBrowser, {
      props: {
        currentPath: 'workspace/output',
        loading: false,
        errorMessage: '',
        items: [
          { name: 'cases', is_dir: true, size: 0, mtime: 1710000000 },
          { name: 'readme.txt', is_dir: false, size: 256, mtime: 1710000001 },
        ],
      },
    })

    expect(wrapper.text()).toContain('workspace')
    expect(wrapper.text()).toContain('output')
    expect(wrapper.text()).toContain('cases')
    expect(wrapper.text()).toContain('readme.txt')

    await wrapper.get('[data-testid="breadcrumb-workspace"]').trigger('click')
    await wrapper.get('[data-testid="entry-open-cases"]').trigger('click')
    await wrapper.get('[data-testid="mkdir-button"]').trigger('click')
    await wrapper.get('[data-testid="download-readme.txt"]').trigger('click')
    await wrapper.get('[data-testid="move-readme.txt"]').trigger('click')
    await wrapper.get('[data-testid="delete-readme.txt"]').trigger('click')

    expect(wrapper.emitted('navigate')?.[0]).toEqual(['workspace'])
    expect(wrapper.emitted('open-directory')?.[0]?.[0]).toMatchObject({ name: 'cases', is_dir: true })
    expect(wrapper.emitted('create-directory')?.[0]).toEqual(['new-folder'])
    expect(wrapper.emitted('download-entry')?.[0]?.[0]).toMatchObject({ name: 'readme.txt', is_dir: false })
    expect(wrapper.emitted('move-entry')?.[0]?.[0]).toEqual({
      sourcePath: 'workspace/output/readme.txt',
      targetPath: 'archive/readme.txt',
    })
    expect(wrapper.emitted('delete-entry')?.[0]?.[0]).toMatchObject({ name: 'readme.txt', is_dir: false })
  })

  it('emits selected files from the upload input', async () => {
    const wrapper = mount(FileBrowser, {
      props: {
        currentPath: '',
        loading: false,
        errorMessage: '',
        items: [],
      },
    })

    const input = wrapper.get('input[type="file"]')
    const file = new File(['abc'], 'demo.txt', { type: 'text/plain' })
    Object.defineProperty(input.element, 'files', {
      value: [file],
      configurable: true,
    })

    await input.trigger('change')

    const emittedFiles = wrapper.emitted('upload-files')?.[0]?.[0] as File[]

    expect(emittedFiles).toHaveLength(1)
    expect(emittedFiles[0]?.name).toBe('demo.txt')
  })
})
