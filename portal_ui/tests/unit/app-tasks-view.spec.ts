import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import AppTasksView from '@/modules/my/views/AppTasksView.vue'
import { myRoutes } from '@/modules/my/routes'

const apiMocks = vi.hoisted(() => ({
  listTasks: vi.fn(),
  getTask: vi.fn(),
  getTaskLogs: vi.fn(),
  getTaskArtifacts: vi.fn(),
  cancelTask: vi.fn(),
}))

vi.mock('@/modules/my/services/api/tasks', () => apiMocks)

function buildRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/my/tasks', component: AppTasksView }],
  })
}

describe('AppTasksView', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    apiMocks.listTasks.mockResolvedValue({
      data: [
        {
          task_id: 'task_1',
          status: 'queued',
          task_kind: 'script_run',
          executor_key: 'ansys',
          entry_path: 'projects/demo/run.py',
          created_at: '2026-04-16 09:00:00',
          assigned_at: null,
          started_at: null,
          ended_at: null,
        },
        {
          task_id: 'task_2',
          status: 'running',
          task_kind: 'script_run',
          executor_key: 'comsol',
          entry_path: 'workspace/Output/task_2/solve.mph',
          created_at: '2026-04-16 09:05:00',
          assigned_at: '2026-04-16 09:06:00',
          started_at: '2026-04-16 09:07:00',
          ended_at: null,
        },
        {
          task_id: 'task_3',
          status: 'succeeded',
          task_kind: 'script_run',
          executor_key: 'abaqus',
          entry_path: 'cases/final/report.inp',
          created_at: '2026-04-15 20:00:00',
          assigned_at: '2026-04-15 20:01:00',
          started_at: '2026-04-15 20:02:00',
          ended_at: '2026-04-15 20:20:00',
        },
      ],
      headers: {},
    } as never)
    apiMocks.getTask.mockResolvedValue({
      data: {
        id: 77,
        task_id: 'task_2',
        status: 'running',
        task_kind: 'script_run',
        executor_key: 'comsol',
        entry_path: 'workspace/Output/task_2/solve.mph',
        workspace_path: 'workspace/Output/task_2',
        input_snapshot_path: 'system/tasks/task_2/input',
        scratch_path: 'system/tasks/task_2/scratch',
        created_at: '2026-04-16 09:05:00',
        assigned_at: '2026-04-16 09:06:00',
        started_at: '2026-04-16 09:07:00',
        ended_at: null,
        cancel_requested: 0,
        result_summary_json: { summary: 'ok' },
      },
      headers: {},
    } as never)
    apiMocks.getTaskLogs.mockResolvedValue({
      data: {
        items: [
          { seq_no: 1, level: 'info', message: 'boot', created_at: '2026-04-16 09:07:00' },
          { seq_no: 2, level: 'info', message: 'running', created_at: '2026-04-16 09:08:00' },
        ],
      },
      headers: {},
    } as never)
    apiMocks.getTaskArtifacts.mockResolvedValue({
      data: {
        items: [
          {
            artifact_kind: 'output',
            display_name: '结果目录',
            relative_path: 'Output/task_2/result.dat',
            minio_bucket: null,
            minio_object_key: null,
            external_url: null,
            size_bytes: 2048,
            created_at: '2026-04-16 09:09:00',
          },
          {
            artifact_kind: 'report',
            display_name: '报告链接',
            relative_path: 'reports/task_2.html',
            minio_bucket: null,
            minio_object_key: null,
            external_url: 'https://example.invalid/report',
            size_bytes: 512,
            created_at: '2026-04-16 09:10:00',
          },
        ],
      },
      headers: {},
    } as never)
    apiMocks.cancelTask.mockResolvedValue({
      data: {
        task_id: 'task_2',
        status: 'cancelled',
        task_kind: 'script_run',
        executor_key: 'comsol',
        entry_path: 'workspace/Output/task_2/solve.mph',
      },
      headers: {},
    } as never)
  })

  it('replaces the placeholder route with the real app tasks view', () => {
    const taskRoute = myRoutes.find((route) => route.path === '/my/tasks')

    expect(taskRoute?.component).toBe(AppTasksView)
  })

  it('loads tasks, filters by status and keyword, and shows task details with workspace link', async () => {
    const router = buildRouter()
    await router.push('/my/tasks')
    await router.isReady()

    const wrapper = mount(AppTasksView, {
      global: {
        plugins: [createPinia(), router],
      },
    })
    await flushPromises()

    expect(apiMocks.listTasks).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('App任务')
    expect(wrapper.text()).toContain('task_1')
    expect(wrapper.text()).toContain('task_2')
    expect(wrapper.text()).toContain('task_3')

    await wrapper.get('[data-testid="task-status-filter"]').setValue('running')
    expect(wrapper.text()).toContain('task_2')
    expect(wrapper.text()).not.toContain('task_1')
    expect(wrapper.text()).not.toContain('task_3')

    await wrapper.get('[data-testid="task-status-filter"]').setValue('all')
    await wrapper.get('[data-testid="task-keyword-filter"]').setValue('report.inp')
    expect(wrapper.text()).toContain('task_3')
    expect(wrapper.text()).not.toContain('task_2')

    await wrapper.get('[data-testid="task-status-filter"]').setValue('all')
    await wrapper.get('[data-testid="task-keyword-filter"]').setValue('solve.mph')
    expect(wrapper.text()).toContain('task_2')

    await wrapper.get('[data-testid="task-open-task_2"]').trigger('click')
    await flushPromises()

    expect(apiMocks.getTask).toHaveBeenCalledWith('task_2')
    expect(apiMocks.getTaskLogs).toHaveBeenCalledWith('task_2')
    expect(apiMocks.getTaskArtifacts).toHaveBeenCalledWith('task_2')
    expect(wrapper.text()).toContain('boot')
    expect(wrapper.text()).toContain('结果目录')
    expect(wrapper.get('[data-testid="artifact-workspace-link-0"]').attributes('href')).toBe('/my/workspace?path=Output%2Ftask_2')
  })

  it('cancels a task from the detail drawer and updates the list', async () => {
    const router = buildRouter()
    await router.push('/my/tasks')
    await router.isReady()

    const wrapper = mount(AppTasksView, {
      global: {
        plugins: [createPinia(), router],
      },
    })
    await flushPromises()

    await wrapper.get('[data-testid="task-open-task_2"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="task-cancel-primary"]').trigger('click')
    await flushPromises()

    expect(apiMocks.cancelTask).toHaveBeenCalledWith('task_2')
    expect(wrapper.text()).toContain('cancelled')
  })

  it('keeps base detail when logs or artifacts fail independently', async () => {
    apiMocks.getTaskLogs.mockRejectedValueOnce(new Error('日志接口失败'))
    apiMocks.getTaskArtifacts.mockRejectedValueOnce(new Error('结果接口失败'))
    const router = buildRouter()
    await router.push('/my/tasks')
    await router.isReady()

    const wrapper = mount(AppTasksView, {
      global: {
        plugins: [createPinia(), router],
      },
    })
    await flushPromises()

    await wrapper.get('[data-testid="task-open-task_2"]').trigger('click')
    await flushPromises()

    expect(apiMocks.getTask).toHaveBeenCalledWith('task_2')
    expect(wrapper.text()).toContain('task_2')
    expect(wrapper.text()).toContain('running')
    expect(wrapper.text()).toContain('workspace/Output/task_2')
    expect(wrapper.text()).toContain('暂无日志')
    expect(wrapper.text()).toContain('暂无结果')
    expect(wrapper.find('[data-testid="artifact-workspace-link-0"]').exists()).toBe(false)
  })
})
