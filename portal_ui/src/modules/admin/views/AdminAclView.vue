<template>
  <section class="admin-ops-view">
    <header class="admin-ops-view__header">
      <div>
        <h1>权限管理</h1>
        <p>活跃用户 × 活跃应用权限矩阵。</p>
      </div>
      <button v-if="users.length && apps.length" type="button" data-testid="admin-acl-save" :disabled="saving" @click="saveAcl">
        {{ saving ? '保存中...' : '保存权限' }}
      </button>
    </header>

    <div v-if="errorMessage" class="admin-ops-view__state admin-ops-view__state--error">{{ errorMessage }}</div>
    <div v-else-if="loading" class="admin-ops-view__state">权限加载中...</div>
    <div v-else-if="users.length === 0 || apps.length === 0" class="admin-ops-view__state">暂无活跃用户或应用</div>
    <table v-else class="admin-ops-view__table admin-acl__table">
      <thead>
        <tr>
          <th>用户 \ 应用</th>
          <th v-for="app in apps" :key="app.id">{{ app.name }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="user in users" :key="user.id">
          <td>{{ user.display_name || user.username }}</td>
          <td v-for="app in apps" :key="app.id">
            <input
              type="checkbox"
              :checked="hasAcl(user.id, app.id)"
              :data-testid="`admin-acl-user-${user.id}-app-${app.id}`"
              @change="toggleAcl(user.id, app.id, $event)"
            >
          </td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { getAdminUserAcl, listAdminUsers, updateAdminUserAcl } from '@/modules/admin/services/api/access'
import { listAdminApps } from '@/modules/admin/services/api/apps'
import type { AdminUserRecord } from '@/modules/admin/types/access'
import type { AdminAppRecord } from '@/modules/admin/types/apps'

const users = ref<AdminUserRecord[]>([])
const apps = ref<AdminAppRecord[]>([])
const aclMap = ref<Record<number, number[]>>({})
const loading = ref(false)
const saving = ref(false)
const errorMessage = ref('')

function hasAcl(userId: number, appId: number) {
  return (aclMap.value[userId] || []).includes(appId)
}

function toggleAcl(userId: number, appId: number, event: Event) {
  const checked = (event.target as HTMLInputElement).checked
  const current = new Set(aclMap.value[userId] || [])
  if (checked) current.add(appId)
  else current.delete(appId)
  aclMap.value = {
    ...aclMap.value,
    [userId]: [...current].sort((left, right) => left - right),
  }
}

async function loadAcl() {
  loading.value = true
  errorMessage.value = ''
  try {
    const [usersResponse, appsResponse] = await Promise.all([listAdminUsers(), listAdminApps()])
    users.value = usersResponse.data.filter((user) => user.is_active)
    apps.value = appsResponse.data.filter((app) => app.is_active)
    const entries = await Promise.all(
      users.value.map(async (user) => {
        const response = await getAdminUserAcl(user.id)
        return [user.id, response.data.app_ids] as const
      }),
    )
    aclMap.value = Object.fromEntries(entries)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '加载权限失败'
  } finally {
    loading.value = false
  }
}

async function saveAcl() {
  saving.value = true
  try {
    for (const user of users.value) {
      await updateAdminUserAcl(user.id, { app_ids: aclMap.value[user.id] || [] })
    }
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  void loadAcl()
})
</script>

<style scoped>
@import './admin-ops.css';

.admin-acl__table th,
.admin-acl__table td {
  text-align: center;
}

.admin-acl__table th:first-child,
.admin-acl__table td:first-child {
  text-align: left;
}
</style>
