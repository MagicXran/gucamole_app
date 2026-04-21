<template>
  <section class="admin-ops-view">
    <header class="admin-ops-view__header">
      <div>
        <h1>审计日志</h1>
        <p>按用户、动作、日期筛选，分页查看。</p>
      </div>
      <button type="button" data-testid="audit-filter-submit" @click="submitFilters">查询</button>
    </header>

    <div class="admin-audit__filters">
      <label><span>用户名</span><input v-model="filters.username" data-testid="audit-filter-username"></label>
      <label>
        <span>动作</span>
        <select v-model="filters.action" data-testid="audit-filter-action">
          <option value="">全部</option>
          <option value="login">登录</option>
          <option value="login_failed">登录失败</option>
          <option value="launch_app">启动应用</option>
          <option value="admin_create_app">创建应用</option>
        </select>
      </label>
      <label><span>开始日期</span><input v-model="filters.date_start" type="date" data-testid="audit-filter-start"></label>
      <label><span>结束日期</span><input v-model="filters.date_end" type="date" data-testid="audit-filter-end"></label>
    </div>

    <div v-if="errorMessage" class="admin-ops-view__state admin-ops-view__state--error">{{ errorMessage }}</div>
    <div v-else-if="loading" class="admin-ops-view__state">审计日志加载中...</div>
    <table v-else class="admin-ops-view__table">
      <thead>
        <tr>
          <th>时间</th>
          <th>用户</th>
          <th>动作</th>
          <th>目标</th>
          <th>IP</th>
          <th>详情</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="items.length === 0">
          <td colspan="6">暂无记录</td>
        </tr>
        <tr v-for="item in items" :key="item.id">
          <td>{{ item.created_at || '' }}</td>
          <td>{{ item.username }}</td>
          <td>{{ actionLabel(item.action) }}</td>
          <td>{{ item.target_name || '-' }}</td>
          <td>{{ item.ip_address || '-' }}</td>
          <td>{{ item.detail || '-' }}</td>
        </tr>
      </tbody>
    </table>

    <div class="admin-audit__pagination">
      <button v-if="page > 1" type="button" data-testid="audit-prev-page" @click="load(page - 1)">上一页</button>
      <span>第 {{ page }} / {{ totalPages }} 页 (共 {{ total }} 条)</span>
      <button v-if="page < totalPages" type="button" data-testid="audit-next-page" @click="load(page + 1)">下一页</button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { getAdminAuditLogs } from '@/modules/admin/services/api/audit'
import type { AdminAuditLog } from '@/modules/admin/types/audit'

const items = ref<AdminAuditLog[]>([])
const loading = ref(false)
const errorMessage = ref('')
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const filters = reactive({
  username: '',
  action: '',
  date_start: '',
  date_end: '',
})

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

function actionLabel(action: string) {
  const labels: Record<string, string> = {
    login: '登录',
    login_failed: '登录失败',
    launch_app: '启动应用',
    admin_create_app: '创建应用',
    admin_update_app: '修改应用',
    admin_delete_app: '禁用应用',
    admin_create_user: '创建用户',
    admin_update_user: '修改用户',
    admin_delete_user: '禁用用户',
    admin_update_acl: '修改权限',
    file_upload: '上传文件',
    file_download: '下载文件',
    file_delete: '删除文件',
  }
  return labels[action] || action
}

async function load(nextPage = 1) {
  loading.value = true
  errorMessage.value = ''
  try {
    const response = await getAdminAuditLogs({
      page: nextPage,
      page_size: pageSize.value,
      username: filters.username.trim() || undefined,
      action: filters.action || undefined,
      date_start: filters.date_start || undefined,
      date_end: filters.date_end || undefined,
    })
    items.value = response.data.items
    total.value = response.data.total
    page.value = response.data.page
    pageSize.value = response.data.page_size
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '加载审计日志失败'
    items.value = []
  } finally {
    loading.value = false
  }
}

async function submitFilters() {
  await load(1)
}

onMounted(() => {
  void load(1)
})
</script>

<style scoped>
@import './admin-ops.css';

.admin-audit__filters,
.admin-audit__pagination {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: flex-end;
}

.admin-audit__filters label {
  display: grid;
  gap: 6px;
}

.admin-audit__pagination {
  justify-content: center;
}

input,
select {
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  padding: 9px 10px;
}
</style>
