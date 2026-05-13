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
          <td colspan="8">暂无运行实例</td>
        </tr>
        <tr v-for="app in adminAppsStore.items" :key="app.id">
          <td>{{ app.id }}</td>
          <td>{{ app.name }}</td>
          <td>{{ launchKindLabel(app.launch_target_kind) }}</td>
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
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
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
  border-radius: 12px;
  background: #f8fafc;
  color: #475569;
}

.admin-apps-view__guard--error {
  background: #fef2f2;
  color: #b91c1c;
}

.admin-apps-view__table {
  width: 100%;
  border-collapse: collapse;
}

.admin-apps-view__table th,
.admin-apps-view__table td {
  padding: 10px 12px;
  border-bottom: 1px solid #e2e8f0;
  text-align: left;
}

.admin-apps-view__actions {
  display: flex;
  gap: 8px;
}

button {
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  background: #fff;
  padding: 8px 10px;
  cursor: pointer;
}
</style>
