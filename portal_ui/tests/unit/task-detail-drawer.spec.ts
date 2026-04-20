import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import TaskDetailDrawer from '@/modules/my/components/TaskDetailDrawer.vue'

describe('TaskDetailDrawer', () => {
  it('renders task detail, logs, artifacts, workspace jump, and emits actions', async () => {
    const wrapper = mount(TaskDetailDrawer, {
      props: {
        open: true,
        loading: false,
        errorMessage: '',
        cancelLoading: false,
        task: {
          task_id: 'task_9',
          status: 'running',
          task_kind: 'script_run',
          executor_key: 'solver',
          entry_path: 'cases/demo/main.py',
          workspace_path: 'workspace/Output/task_9',
          input_snapshot_path: 'system/tasks/task_9/input',
          scratch_path: 'system/tasks/task_9/scratch',
          created_at: '2026-04-16 10:00:00',
          assigned_at: '2026-04-16 10:01:00',
          started_at: '2026-04-16 10:02:00',
          ended_at: null,
          cancel_requested: 0,
          result_summary_json: { state: 'running' },
        },
        logs: [
          { seq_no: 1, level: 'info', message: 'hello', created_at: '2026-04-16 10:03:00' },
        ],
        artifacts: [
          {
            artifact_kind: 'output',
            display_name: '输出文件',
            relative_path: 'Output/task_9/result.csv',
            minio_bucket: null,
            minio_object_key: null,
            external_url: null,
            size_bytes: 1024,
            created_at: '2026-04-16 10:05:00',
          },
          {
            artifact_kind: 'report',
            display_name: 'Web 报告',
            relative_path: 'reports/task_9/index.html',
            minio_bucket: null,
            minio_object_key: null,
            external_url: 'https://example.invalid/report',
            size_bytes: 2048,
            created_at: '2026-04-16 10:06:00',
          },
        ],
      },
    })

    expect(wrapper.text()).toContain('task_9')
    expect(wrapper.text()).toContain('hello')
    expect(wrapper.text()).toContain('输出文件')
    expect(wrapper.text()).toContain('Web 报告')
    expect(wrapper.get('[data-testid="artifact-workspace-link-0"]').attributes('href')).toBe('/my/workspace?path=Output%2Ftask_9')
    expect(wrapper.find('[data-testid="artifact-workspace-link-1"]').exists()).toBe(false)

    await wrapper.get('[data-testid="task-cancel-primary"]').trigger('click')
    await wrapper.get('[data-testid="task-detail-close"]').trigger('click')

    expect(wrapper.emitted('cancel-task')).toEqual([['task_9']])
    expect(wrapper.emitted('close')).toHaveLength(1)
  })
})
