<template>
  <section class="admin-ops-view">
    <header class="admin-ops-view__header">
      <div>
        <h1>Worker状态</h1>
        <p>节点组、节点状态、注册码、凭证和软件能力。这里只读，那就是半残。</p>
      </div>
      <div class="admin-workers__toolbar">
        <button type="button" data-testid="admin-worker-create-group" @click="openGroupDialog">新建节点组</button>
        <button type="button" data-testid="admin-worker-create-node" @click="openNodeDialog">预建节点</button>
        <button type="button" @click="workersStore.loadWorkers">刷新</button>
      </div>
    </header>

    <div v-if="workersStore.errorMessage" class="admin-ops-view__state admin-ops-view__state--error">
      {{ workersStore.errorMessage }}
    </div>
    <template v-else>
      <section class="admin-workers__guide">
        <article v-for="card in guideCards" :key="card.step" class="admin-workers__guide-card">
          <strong>{{ card.step }}</strong>
          <span>{{ card.title }}</span>
          <small>{{ card.desc }}</small>
        </article>
      </section>

      <section class="admin-ops-view__cards">
        <article v-for="group in workersStore.groups" :key="group.id" class="admin-ops-view__card">
          <strong>{{ group.name }}</strong>
          <span>{{ group.active_node_count }} 在线 / {{ group.node_count }} 总数</span>
          <small>{{ group.description || group.group_key }}</small>
        </article>
      </section>

      <table class="admin-ops-view__table">
        <thead>
          <tr>
            <th>节点</th>
            <th>节点组</th>
            <th>注册 / 心跳</th>
            <th>路径配置</th>
            <th>软件能力</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="workersStore.nodes.length === 0">
            <td colspan="6">暂无 Worker 节点</td>
          </tr>
          <tr v-for="node in workersStore.nodes" :key="node.id">
            <td>
              <strong>{{ node.display_name || `worker_${node.id}` }}</strong>
              <div class="admin-workers__meta">{{ node.expected_hostname || '-' }}</div>
            </td>
            <td>{{ node.group_name }}</td>
            <td>
              <span :class="['admin-workers__badge', readinessMeta(node).tone]">{{ readinessMeta(node).summary }}</span>
              <div class="admin-workers__meta">{{ readinessMeta(node).detail }}</div>
            </td>
            <td>
              <div>工作区：<code>{{ node.workspace_share || '-' }}</code></div>
              <div>Scratch：<code>{{ node.scratch_root || '-' }}</code></div>
              <div>并发：{{ node.max_concurrent_tasks || 1 }}</div>
            </td>
            <td>
              <strong>{{ softwareSummary(node) }}</strong>
              <div class="admin-workers__meta">能力详情里可看每个软件的 issues</div>
            </td>
            <td class="admin-workers__actions">
              <button type="button" :data-testid="`admin-worker-inventory-${node.id}`" @click="openInventoryDialog(node)">能力详情</button>
              <button type="button" :data-testid="`admin-worker-enrollment-${node.id}`" @click="issueEnrollment(node.id)">签发注册码</button>
              <button type="button" :data-testid="`admin-worker-rotate-token-${node.id}`" @click="rotateToken(node.id)">轮换凭证</button>
              <button type="button" :data-testid="`admin-worker-revoke-${node.id}`" @click="revokeNode(node.id)">吊销</button>
            </td>
          </tr>
        </tbody>
      </table>
    </template>

    <div v-if="dialog.kind" class="admin-workers__dialog">
      <div class="admin-workers__panel">
        <header class="admin-workers__panel-header">
          <h2>{{ dialogTitle }}</h2>
          <button type="button" @click="closeDialog">关闭</button>
        </header>

        <form v-if="dialog.kind === 'group'" class="admin-workers__form" @submit.prevent="submitGroup">
          <label>
            <span>组键</span>
            <input v-model="groupForm.group_key" data-testid="worker-group-key" required>
          </label>
          <label>
            <span>名称</span>
            <input v-model="groupForm.name" data-testid="worker-group-name" required>
          </label>
          <label>
            <span>说明</span>
            <input v-model="groupForm.description" data-testid="worker-group-desc">
          </label>
          <label>
            <span>每次认领批量</span>
            <input v-model.number="groupForm.max_claim_batch" type="number" min="1" data-testid="worker-group-batch" required>
          </label>
          <footer class="admin-workers__panel-actions">
            <button type="button" @click="closeDialog">取消</button>
            <button type="button" data-testid="worker-group-submit" :disabled="workersStore.saving" @click="submitGroup">创建</button>
          </footer>
        </form>

        <form v-else-if="dialog.kind === 'node'" class="admin-workers__form" @submit.prevent="submitNode">
          <label>
            <span>节点组</span>
            <select v-model="nodeForm.group_id" data-testid="worker-node-group-id" required>
              <option v-for="group in workersStore.groups" :key="group.id" :value="group.id">{{ group.name }}</option>
            </select>
          </label>
          <label>
            <span>显示名称</span>
            <input v-model="nodeForm.display_name" data-testid="worker-node-display-name" required>
          </label>
          <label>
            <span>期望主机名</span>
            <input v-model="nodeForm.expected_hostname" data-testid="worker-node-expected-hostname" required>
          </label>
          <label>
            <span>本地 scratch 根目录</span>
            <input v-model="nodeForm.scratch_root" data-testid="worker-node-scratch-root" required>
          </label>
          <label>
            <span>共享工作区 UNC</span>
            <input v-model="nodeForm.workspace_share" data-testid="worker-node-workspace-share" required>
          </label>
          <label>
            <span>本机并发上限</span>
            <input v-model.number="nodeForm.max_concurrent_tasks" type="number" min="1" data-testid="worker-node-max-concurrent" required>
          </label>
          <footer class="admin-workers__panel-actions">
            <button type="button" @click="closeDialog">取消</button>
            <button type="button" data-testid="worker-node-submit" :disabled="workersStore.saving" @click="submitNode">创建</button>
          </footer>
        </form>

        <div v-else-if="dialog.kind === 'inventory'" class="admin-workers__inventory">
          <div v-if="inventoryItems.length === 0" class="admin-workers__empty">节点尚未上报软件能力</div>
          <article v-for="item in inventoryItems" :key="item.key" class="admin-workers__inventory-item">
            <strong>{{ item.name }}</strong>
            <span :class="['admin-workers__badge', item.ready ? 'admin-workers__badge--active' : 'admin-workers__badge--inactive']">
              {{ item.ready ? '就绪' : '未就绪' }}
            </span>
            <div class="admin-workers__meta">{{ item.issues }}</div>
          </article>
        </div>

        <div v-else-if="dialog.kind === 'token'" class="admin-workers__token">
          <div class="admin-workers__token-value">{{ dialog.plainToken }}</div>
          <label>
            <span>{{ dialogTokenLabel }}</span>
            <input :value="dialog.plainToken" readonly>
          </label>
          <label v-if="dialog.expiresAt">
            <span>过期时间</span>
            <input :value="dialog.expiresAt" readonly>
          </label>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive } from 'vue'

import { useAdminWorkersStore } from '@/modules/admin/stores/workers'
import type { AdminWorkerNode, AdminWorkerSoftwareItem } from '@/modules/admin/types/ops'

const workersStore = useAdminWorkersStore()

const guideCards = [
  { step: 'Step 1', title: '先建节点组', desc: '把同一类软件环境的机器归成一组。' },
  { step: 'Step 2', title: '再预建节点', desc: '主机名、共享工作区和 scratch 路径必须真实可访问。' },
  { step: 'Step 3', title: '最后绑应用', desc: '应用启用脚本模式后再绑定软件预设、执行器和 Worker 组。' },
]

const groupForm = reactive({
  group_key: '',
  name: '',
  description: '',
  max_claim_batch: 1,
})

const nodeForm = reactive({
  group_id: 0,
  display_name: '',
  expected_hostname: '',
  scratch_root: 'C:\\sim-work',
  workspace_share: '\\\\sim-fs\\workspaces',
  max_concurrent_tasks: 1,
})

const dialog = reactive<{
  kind: '' | 'group' | 'node' | 'inventory' | 'token'
  node: AdminWorkerNode | null
  tokenKind: '' | 'enrollment' | 'access'
  plainToken: string
  expiresAt: string
}>({
  kind: '',
  node: null,
  tokenKind: '',
  plainToken: '',
  expiresAt: '',
})

const dialogTitle = computed(() => {
  if (dialog.kind === 'group') return '新建节点组'
  if (dialog.kind === 'node') return '预建 Worker 节点'
  if (dialog.kind === 'inventory') return `软件能力 · ${dialog.node?.display_name || `worker_${dialog.node?.id || ''}`}`
  if (dialog.kind === 'token') return dialog.tokenKind === 'enrollment' ? 'Worker 注册码' : 'Worker 访问凭证'
  return ''
})

const dialogTokenLabel = computed(() => (dialog.tokenKind === 'enrollment' ? 'Enrollment Token' : 'Access Token'))

const inventoryItems = computed(() => {
  const inventory = dialog.node?.software_inventory || {}
  return Object.entries(inventory).map(([key, value]: [string, AdminWorkerSoftwareItem]) => ({
    key,
    name: value.software_name || key,
    ready: Boolean(value.ready),
    issues: value.issues?.length ? value.issues.join(', ') : '无',
  }))
})

function readinessMeta(node: AdminWorkerNode) {
  const details: string[] = []
  let summary = node.status || 'unknown'
  let tone = 'admin-workers__badge--inactive'

  if (node.status === 'pending_enrollment') {
    summary = '待注册'
    details.push('先签发注册码，再去对应 Windows 主机注册')
  } else if (node.status === 'active') {
    summary = '在线'
    tone = 'admin-workers__badge--active'
    details.push(`最近心跳：${node.last_heartbeat_at || '未上报'}`)
  } else if (node.status === 'offline') {
    summary = '离线'
    details.push(`最后心跳：${node.last_heartbeat_at || '未上报'}`)
  } else if (node.status === 'revoked') {
    summary = '已吊销'
    details.push('当前凭证已失效，需要重新签发')
  }

  if (node.latest_enrollment_status) {
    details.push(`注册码：${node.latest_enrollment_status}${node.latest_enrollment_expires_at ? `，到期 ${node.latest_enrollment_expires_at}` : ''}`)
  }
  if (node.software_total_count > 0) {
    details.push(`软件就绪：${node.software_ready_count}/${node.software_total_count}`)
  } else {
    details.push('软件能力：尚未上报')
  }
  if (node.last_error) {
    details.push(`最近错误：${node.last_error}`)
  }

  return {
    summary,
    tone,
    detail: details.join(' · '),
  }
}

function softwareSummary(node: AdminWorkerNode) {
  return node.software_total_count ? `${node.software_ready_count}/${node.software_total_count} 就绪` : '未上报'
}

function closeDialog() {
  dialog.kind = ''
  dialog.node = null
  dialog.tokenKind = ''
  dialog.plainToken = ''
  dialog.expiresAt = ''
}

function openGroupDialog() {
  groupForm.group_key = ''
  groupForm.name = ''
  groupForm.description = ''
  groupForm.max_claim_batch = 1
  dialog.kind = 'group'
}

function openNodeDialog() {
  nodeForm.group_id = workersStore.groups[0]?.id || 0
  nodeForm.display_name = ''
  nodeForm.expected_hostname = ''
  nodeForm.scratch_root = 'C:\\sim-work'
  nodeForm.workspace_share = '\\\\sim-fs\\workspaces'
  nodeForm.max_concurrent_tasks = 1
  dialog.kind = 'node'
}

function openInventoryDialog(node: AdminWorkerNode) {
  dialog.node = node
  dialog.kind = 'inventory'
}

async function submitGroup() {
  await workersStore.saveWorkerGroup({
    group_key: groupForm.group_key.trim(),
    name: groupForm.name.trim(),
    description: groupForm.description.trim(),
    max_claim_batch: Number(groupForm.max_claim_batch) || 1,
  })
  closeDialog()
}

async function submitNode() {
  await workersStore.saveWorkerNode({
    group_id: Number(nodeForm.group_id),
    display_name: nodeForm.display_name.trim(),
    expected_hostname: nodeForm.expected_hostname.trim(),
    scratch_root: nodeForm.scratch_root.trim(),
    workspace_share: nodeForm.workspace_share.trim(),
    max_concurrent_tasks: Number(nodeForm.max_concurrent_tasks) || 1,
  })
  closeDialog()
}

async function issueEnrollment(workerNodeId: number) {
  const result = await workersStore.issueEnrollment(workerNodeId)
  dialog.kind = 'token'
  dialog.tokenKind = 'enrollment'
  dialog.plainToken = result.plain_token
  dialog.expiresAt = result.expires_at || ''
}

async function rotateToken(workerNodeId: number) {
  const result = await workersStore.rotateToken(workerNodeId)
  dialog.kind = 'token'
  dialog.tokenKind = 'access'
  dialog.plainToken = result.plain_token
  dialog.expiresAt = ''
}

async function revokeNode(workerNodeId: number) {
  if (typeof window.confirm === 'function' && !window.confirm('确定吊销这个 Worker 节点？')) {
    return
  }
  await workersStore.revokeNode(workerNodeId)
}

onMounted(async () => {
  await workersStore.loadWorkers()
})
</script>

<style scoped>
@import './admin-ops.css';

.admin-workers__toolbar,
.admin-workers__actions,
.admin-workers__panel-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.admin-workers__guide {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}

.admin-workers__guide-card,
.admin-workers__inventory-item {
  display: grid;
  gap: 6px;
  padding: 14px;
  border: 1px solid #dbe4f0;
  border-radius: 12px;
  background: #f8fafc;
}

.admin-workers__meta {
  color: #64748b;
  font-size: 13px;
  line-height: 1.5;
}

.admin-workers__badge {
  display: inline-block;
  width: fit-content;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 12px;
  background: #fee2e2;
  color: #991b1b;
}

.admin-workers__badge--active {
  background: #dcfce7;
  color: #166534;
}

.admin-workers__badge--inactive {
  background: #fee2e2;
  color: #991b1b;
}

.admin-workers__dialog {
  position: fixed;
  inset: 0;
  z-index: 20;
  display: grid;
  place-items: center;
  background: rgba(15, 23, 42, 0.45);
}

.admin-workers__panel {
  width: min(760px, calc(100vw - 32px));
  max-height: calc(100vh - 32px);
  overflow: auto;
  display: grid;
  gap: 16px;
  padding: 24px;
  border-radius: 18px;
  background: #fff;
}

.admin-workers__panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.admin-workers__panel-header h2 {
  margin: 0;
}

.admin-workers__form,
.admin-workers__token {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.admin-workers__form label,
.admin-workers__token label {
  display: grid;
  gap: 6px;
}

.admin-workers__panel-actions {
  grid-column: 1 / -1;
  justify-content: flex-end;
}

.admin-workers__inventory {
  display: grid;
  gap: 10px;
}

.admin-workers__empty {
  padding: 14px;
  border-radius: 12px;
  background: #f8fafc;
  color: #64748b;
}

.admin-workers__token-value {
  grid-column: 1 / -1;
  padding: 12px;
  border-radius: 10px;
  background: #f1f5f9;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  word-break: break-all;
}

input,
select {
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  padding: 9px 10px;
}

code {
  padding: 1px 4px;
  border-radius: 4px;
  background: #f1f5f9;
}

@media (max-width: 720px) {
  .admin-workers__form,
  .admin-workers__token {
    grid-template-columns: 1fr;
  }
}
</style>
