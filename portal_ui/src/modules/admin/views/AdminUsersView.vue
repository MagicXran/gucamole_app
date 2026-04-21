<template>
  <section class="admin-ops-view">
    <header class="admin-ops-view__header">
      <div>
        <h1>用户管理</h1>
        <p>账号、改密、配额、管理员权限和启停状态。</p>
      </div>
      <button type="button" data-testid="admin-user-create" @click="openCreate">新建用户</button>
    </header>

    <div v-if="errorMessage" class="admin-ops-view__state admin-ops-view__state--error">{{ errorMessage }}</div>
    <div v-else-if="loading" class="admin-ops-view__state">用户加载中...</div>
    <table v-else class="admin-ops-view__table">
      <thead>
        <tr>
          <th>ID</th>
          <th>用户名</th>
          <th>显示名称</th>
          <th>角色</th>
          <th>个人空间</th>
          <th>状态</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="users.length === 0">
          <td colspan="7">暂无用户</td>
        </tr>
        <tr v-for="user in users" :key="user.id">
          <td>{{ user.id }}</td>
          <td>{{ user.username }}</td>
          <td>{{ user.display_name }}</td>
          <td>{{ user.is_admin ? '管理员' : '普通用户' }}</td>
          <td>{{ user.used_display || '0 B' }} / {{ user.quota_display || quotaBytesToLabel(user.quota_bytes) }}</td>
          <td>{{ user.is_active ? '正常' : '已禁用' }}</td>
          <td class="admin-users__actions">
            <button type="button" :data-testid="`admin-user-edit-${user.id}`" @click="openEdit(user)">编辑</button>
            <button v-if="user.is_active" type="button" @click="removeUser(user.id)">禁用</button>
          </td>
        </tr>
      </tbody>
    </table>

    <div v-if="dialogOpen" class="admin-users__dialog">
      <div class="admin-users__panel">
        <header class="admin-users__panel-header">
          <h2>{{ dialogMode === 'edit' ? '编辑用户' : '新建用户' }}</h2>
          <button type="button" @click="closeDialog">关闭</button>
        </header>

        <p v-if="dialogError" class="admin-users__error">{{ dialogError }}</p>

        <div class="admin-users__form">
          <label v-if="dialogMode === 'create'"><span>用户名</span><input v-model="form.username" data-testid="admin-user-username"></label>
          <label v-else><span>用户名</span><input :value="selectedUser?.username || ''" disabled data-testid="admin-user-username-disabled"></label>
          <label><span>{{ dialogMode === 'edit' ? '新密码（留空不改）' : '密码' }}</span><input v-model="form.password" type="password" autocomplete="new-password" data-testid="admin-user-password"></label>
          <label><span>显示名称</span><input v-model="form.display_name" data-testid="admin-user-display"></label>
          <label>
            <span>个人空间配额</span>
            <select v-model="form.quotaLabel" data-testid="admin-user-quota">
              <option v-for="option in quotaOptions" :key="option" :value="option">{{ option }}</option>
            </select>
          </label>
          <label class="admin-users__checkbox"><input v-model="form.is_admin" type="checkbox" data-testid="admin-user-is-admin"><span>管理员</span></label>
          <label v-if="dialogMode === 'edit'" class="admin-users__checkbox"><input v-model="form.is_active" type="checkbox" data-testid="admin-user-is-active"><span>启用</span></label>
        </div>

        <footer class="admin-users__panel-actions">
          <button type="button" @click="closeDialog">取消</button>
          <button type="button" data-testid="admin-user-submit" :disabled="saving" @click="submitForm">{{ saving ? '保存中...' : '保存' }}</button>
        </footer>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { createAdminUser, deleteAdminUser, listAdminUsers, updateAdminUser } from '@/modules/admin/services/api/access'
import type { AdminUserCreatePayload, AdminUserRecord, AdminUserUpdatePayload } from '@/modules/admin/types/access'

const quotaOptions = ['默认(10GB)', '5 GB', '10 GB', '20 GB', '50 GB', '100 GB', '不限制']
const users = ref<AdminUserRecord[]>([])
const loading = ref(false)
const saving = ref(false)
const errorMessage = ref('')
const dialogError = ref('')
const dialogOpen = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const selectedUser = ref<AdminUserRecord | null>(null)

const form = reactive({
  username: '',
  password: '',
  display_name: '',
  quotaLabel: '默认(10GB)',
  is_admin: false,
  is_active: true,
})

function quotaBytesToLabel(bytes: number | null | undefined) {
  if (!bytes) return '默认(10GB)'
  const gb = bytes / 1073741824
  if (gb >= 9000) return '不限制'
  if (gb <= 5) return '5 GB'
  if (gb <= 10) return '10 GB'
  if (gb <= 20) return '20 GB'
  if (gb <= 50) return '50 GB'
  if (gb <= 100) return '100 GB'
  return '不限制'
}

function quotaLabelToGb(label: string) {
  if (label === '不限制') return 9999
  if (label === '默认(10GB)') return 0
  const matched = label.match(/(\d+)/)
  return matched ? Number.parseInt(matched[1], 10) : 0
}

function resetForm() {
  form.username = ''
  form.password = ''
  form.display_name = ''
  form.quotaLabel = '默认(10GB)'
  form.is_admin = false
  form.is_active = true
  dialogError.value = ''
}

function closeDialog() {
  dialogOpen.value = false
  selectedUser.value = null
  resetForm()
}

function openCreate() {
  dialogMode.value = 'create'
  selectedUser.value = null
  resetForm()
  dialogOpen.value = true
}

function openEdit(user: AdminUserRecord) {
  dialogMode.value = 'edit'
  selectedUser.value = user
  form.username = user.username
  form.password = ''
  form.display_name = user.display_name
  form.quotaLabel = quotaBytesToLabel(user.quota_bytes)
  form.is_admin = user.is_admin
  form.is_active = user.is_active
  dialogError.value = ''
  dialogOpen.value = true
}

async function loadUsers() {
  loading.value = true
  errorMessage.value = ''
  try {
    const response = await listAdminUsers()
    users.value = response.data
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '加载用户失败'
    users.value = []
  } finally {
    loading.value = false
  }
}

async function submitForm() {
  dialogError.value = ''
  const quotaGb = quotaLabelToGb(form.quotaLabel)
  const displayName = form.display_name.trim()

  if (dialogMode.value === 'create') {
    const username = form.username.trim()
    if (!username || !form.password) {
      dialogError.value = '用户名和密码为必填项'
      return
    }
    const payload: AdminUserCreatePayload = {
      username,
      password: form.password,
      display_name: displayName || username,
      is_admin: form.is_admin,
      quota_gb: quotaGb,
    }
    saving.value = true
    try {
      await createAdminUser(payload)
      await loadUsers()
      closeDialog()
    } finally {
      saving.value = false
    }
    return
  }

  if (!selectedUser.value) return
  const payload: AdminUserUpdatePayload = {
    display_name: displayName || selectedUser.value.display_name,
    is_admin: form.is_admin,
    is_active: form.is_active,
    quota_gb: quotaGb,
  }
  if (form.password) payload.password = form.password

  saving.value = true
  try {
    await updateAdminUser(selectedUser.value.id, payload)
    await loadUsers()
    closeDialog()
  } finally {
    saving.value = false
  }
}

async function removeUser(userId: number) {
  if (typeof window.confirm === 'function' && !window.confirm('确定要禁用此用户？')) return
  await deleteAdminUser(userId)
  await loadUsers()
}

onMounted(() => {
  void loadUsers()
})
</script>

<style scoped>
@import './admin-ops.css';

.admin-users__actions,
.admin-users__panel-header,
.admin-users__panel-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  justify-content: space-between;
}

.admin-users__dialog {
  position: fixed;
  inset: 0;
  display: grid;
  place-items: center;
  background: rgba(15, 23, 42, 0.45);
  z-index: 20;
}

.admin-users__panel {
  width: min(720px, calc(100vw - 32px));
  display: grid;
  gap: 16px;
  padding: 24px;
  border-radius: 18px;
  background: #fff;
}

.admin-users__panel-header h2 {
  margin: 0;
}

.admin-users__form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.admin-users__form label {
  display: grid;
  gap: 6px;
}

.admin-users__checkbox {
  display: flex !important;
  align-items: center;
  gap: 8px !important;
  align-self: end;
}

.admin-users__error {
  margin: 0;
  padding: 10px 12px;
  border-radius: 10px;
  background: #fef2f2;
  color: #b91c1c;
}

input,
select {
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  padding: 9px 10px;
}
</style>
