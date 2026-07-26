<template>
  <section class="admin-apps-view">
    <header class="admin-apps-view__header">
      <div>
        <h1>运行实例管理</h1>
        <p>维护具体 RemoteApp/RDP 运行实例、脚本绑定和容量池归属。</p>
      </div>
      <button
        v-if="isAdmin"
        type="button"
        data-testid="admin-app-create"
        @click="openCreate"
      >
        新建应用
      </button>
    </header>

    <div v-if="!isAdmin" class="admin-apps-view__guard">仅管理员可操作</div>
    <div v-else-if="adminAppsStore.errorMessage" class="admin-apps-view__guard admin-apps-view__guard--error">
      {{ adminAppsStore.errorMessage }}
    </div>
    <div v-else-if="adminAppsStore.loading" class="admin-apps-view__guard">运行实例加载中...</div>
    <table v-else class="admin-apps-view__table">
      <thead>
        <tr>
          <th>ID</th>
          <th>名称</th>
          <th>形态</th>
          <th>安全模式</th>
          <th>分类</th>
          <th>主机</th>
          <th>容量池</th>
          <th>健康</th>
          <th>状态</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="adminAppsStore.items.length === 0">
          <td colspan="10">暂无运行实例</td>
        </tr>
        <tr v-for="app in adminAppsStore.items" :key="app.id">
          <td>{{ app.id }}</td>
          <td>{{ app.name }}</td>
          <td>{{ launchKindLabel(app.launch_target_kind) }}</td>
          <td>{{ securityModeLabel(app.security_mode) }}</td>
          <td>{{ kindLabel(app.app_kind) }}</td>
          <td>{{ app.hostname }}:{{ app.port }}</td>
          <td>{{ poolName(app.pool_id) }}</td>
          <td>{{ app.runtime_health_status_label || '未探测' }}</td>
          <td>{{ app.is_active ? '启用' : '禁用' }}</td>
          <td class="admin-apps-view__actions">
            <button type="button" :data-testid="`admin-app-edit-${app.id}`" @click="openEdit(app)">编辑</button>
            <button type="button" @click="removeApp(app.id)">删除</button>
          </td>
        </tr>
      </tbody>
    </table>

    <AdminAppFormDialog
      :open="dialogOpen"
      :mode="dialogMode"
      :saving="adminAppsStore.saving"
      :pools="adminAppsStore.pools"
      :worker-groups="adminAppsStore.workerGroups"
      :script-profiles="adminAppsStore.scriptProfiles"
      :vscode-control-profiles="adminAppsStore.vscodeControlProfiles"
      :initial-app="selectedApp"
      @close="closeDialog"
      @submit="handleSubmit"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import AdminAppFormDialog from '@/modules/admin/components/AdminAppFormDialog.vue'
import { useAdminAppsStore } from '@/modules/admin/stores/apps'
import type { AdminAppFormPayload, AdminAppRecord } from '@/modules/admin/types/apps'
import { useSessionStore } from '@/stores/session'

const sessionStore = useSessionStore()
const adminAppsStore = useAdminAppsStore()

const dialogOpen = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const selectedApp = ref<AdminAppRecord | null>(null)

const isAdmin = computed(() => Boolean(sessionStore.user?.is_admin))

function kindLabel(kind: string) {
  if (kind === 'simulation_app') return '仿真APP'
  if (kind === 'compute_tool') return '计算工具'
  return '商业软件'
}

function launchKindLabel(kind: string | undefined) {
  return kind === 'standalone_runtime' ? '独立运行' : '容量池成员'
}

function securityModeLabel(mode: string | undefined) {
  if (mode === 'restricted_vscode') return '受限 VSCode'
  if (mode === 'admin_desktop') return '管理员桌面'
  return '一般限制 RemoteApp'
}

function poolName(poolId: number | null) {
  return adminAppsStore.pools.find((pool) => pool.id === poolId)?.name || '独立运行'
}

function closeDialog() {
  dialogOpen.value = false
  selectedApp.value = null
}

function openCreate() {
  dialogMode.value = 'create'
  selectedApp.value = null
  dialogOpen.value = true
}

function openEdit(app: AdminAppRecord) {
  dialogMode.value = 'edit'
  selectedApp.value = app
  dialogOpen.value = true
}

async function handleSubmit({
  appId,
  payload,
}: {
  appId: number | null
  payload: AdminAppFormPayload
}) {
  await adminAppsStore.saveApp(appId, payload)
  closeDialog()
}

async function removeApp(appId: number) {
  if (typeof window.confirm === 'function' && !window.confirm('确定删除这个应用？')) {
    return
  }
  await adminAppsStore.removeApp(appId)
}

onMounted(async () => {
  await adminAppsStore.bootstrap()
})
</script>

<style scoped>
.admin-apps-view {
  display: grid;
  gap: 18px;
  padding: 24px;
  background: var(--portal-color-surface);
  border: 1px solid var(--portal-color-border);
  border-radius: 24px;
  box-shadow: var(--portal-shadow-soft);
}

.admin-apps-view__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.admin-apps-view__header h1,
.admin-apps-view__header p {
  margin: 0;
}

.admin-apps-view__guard {
  padding: 16px;
  border-radius: 18px;
  background: var(--portal-color-surface-soft);
  color: var(--portal-color-body);
}

.admin-apps-view__guard--error {
  background: #fff5f7;
  color: var(--portal-color-danger);
}

.admin-apps-view__table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  overflow: hidden;
  border: 1px solid var(--portal-color-border);
  border-radius: 20px;
  background: var(--portal-color-surface);
}

.admin-apps-view__table th,
.admin-apps-view__table td {
  padding: 10px 12px;
  border-bottom: 1px solid var(--portal-color-border);
  text-align: left;
}

.admin-apps-view__table th {
  background: var(--portal-color-page);
  color: var(--portal-color-muted);
  font-size: 12px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.admin-apps-view__actions {
  display: flex;
  gap: 8px;
}

button {
  min-height: 40px;
  border: 1px solid var(--portal-color-border);
  border-radius: 999px;
  background: var(--portal-color-surface);
  color: var(--portal-color-ink);
  padding: 0 14px;
  cursor: pointer;
  transition: border-color 0.2s ease, color 0.2s ease, background 0.2s ease;
}

button:hover {
  border-color: var(--portal-color-primary);
  color: var(--portal-color-primary);
}
</style>
