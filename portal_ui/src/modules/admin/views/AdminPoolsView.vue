<template>
  <section class="admin-ops-view">
    <header class="admin-ops-view__header">
      <div>
        <h1>资源池</h1>
        <p>池级并发、自动放行、ready 宽限、失联/空闲回收策略。</p>
      </div>
      <button type="button" data-testid="admin-pool-create" @click="openCreate">新建资源池</button>
    </header>

    <div v-if="errorMessage" class="admin-ops-view__state admin-ops-view__state--error">{{ errorMessage }}</div>
    <div v-else-if="loading" class="admin-ops-view__state">资源池加载中...</div>
    <table v-else class="admin-ops-view__table">
      <thead>
        <tr>
          <th>ID</th>
          <th>名称</th>
          <th>容量</th>
          <th>运行中</th>
          <th>排队中</th>
          <th>自动放行</th>
          <th>回收策略</th>
          <th>状态</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="pools.length === 0">
          <td colspan="9">暂无资源池</td>
        </tr>
        <tr v-for="pool in pools" :key="pool.id">
          <td>{{ pool.id }}</td>
          <td>{{ pool.name }}</td>
          <td>{{ pool.max_concurrent }}</td>
          <td>{{ pool.active_count }}</td>
          <td>{{ pool.queued_count }}</td>
          <td>{{ pool.auto_dispatch_enabled ? '启用' : '禁用' }}</td>
          <td>ready {{ pool.dispatch_grace_seconds }}s · 失联 {{ pool.stale_timeout_seconds }}s · 空闲 {{ pool.idle_timeout_seconds || '-' }}s</td>
          <td>{{ pool.is_active ? '启用' : '禁用' }}</td>
          <td><button type="button" :data-testid="`admin-pool-edit-${pool.id}`" @click="openEdit(pool)">编辑</button></td>
        </tr>
      </tbody>
    </table>

    <div v-if="dialogOpen" class="admin-pools__dialog">
      <div class="admin-pools__panel">
        <header class="admin-pools__panel-header">
          <h2>{{ selectedPool ? '编辑资源池' : '新建资源池' }}</h2>
          <button type="button" @click="closeDialog">关闭</button>
        </header>
        <div class="admin-pools__form">
          <label><span>名称</span><input v-model="form.name" data-testid="admin-pool-name"></label>
          <label><span>图标</span><input v-model="form.icon" data-testid="admin-pool-icon"></label>
          <label><span>总并发上限</span><input v-model.number="form.max_concurrent" type="number" min="1" data-testid="admin-pool-max"></label>
          <label><span>ready 宽限(秒)</span><input v-model.number="form.dispatch_grace_seconds" type="number" min="10" data-testid="admin-pool-grace"></label>
          <label><span>失联回收(秒)</span><input v-model.number="form.stale_timeout_seconds" type="number" min="30" data-testid="admin-pool-stale"></label>
          <label><span>空闲回收(秒, 留空禁用)</span><input v-model="form.idle_timeout_seconds" type="number" data-testid="admin-pool-idle"></label>
          <label class="admin-pools__checkbox"><input v-model="form.auto_dispatch_enabled" type="checkbox" data-testid="admin-pool-auto"><span>启用自动放行</span></label>
          <label class="admin-pools__checkbox"><input v-model="form.is_active" type="checkbox" data-testid="admin-pool-active"><span>启用</span></label>
        </div>
        <footer class="admin-pools__panel-actions">
          <button type="button" @click="closeDialog">取消</button>
          <button type="button" data-testid="admin-pool-submit" :disabled="saving" @click="submitPool">保存</button>
        </footer>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { createAdminPool, listAdminPools, updateAdminPool } from '@/modules/admin/services/api/pools'
import type { AdminPoolPayload, AdminPoolRecord } from '@/modules/admin/types/pools'

const pools = ref<AdminPoolRecord[]>([])
const loading = ref(false)
const saving = ref(false)
const errorMessage = ref('')
const dialogOpen = ref(false)
const selectedPool = ref<AdminPoolRecord | null>(null)

const form = reactive({
  name: '',
  icon: 'desktop',
  max_concurrent: 1,
  auto_dispatch_enabled: true,
  dispatch_grace_seconds: 120,
  stale_timeout_seconds: 120,
  idle_timeout_seconds: '' as string | number,
  is_active: true,
})

function fillForm(pool: AdminPoolRecord | null) {
  form.name = pool?.name || ''
  form.icon = pool?.icon || 'desktop'
  form.max_concurrent = pool?.max_concurrent || 1
  form.auto_dispatch_enabled = pool?.auto_dispatch_enabled ?? true
  form.dispatch_grace_seconds = pool?.dispatch_grace_seconds || 120
  form.stale_timeout_seconds = pool?.stale_timeout_seconds || 120
  form.idle_timeout_seconds = pool?.idle_timeout_seconds || ''
  form.is_active = pool?.is_active ?? true
}

function buildPayload(): AdminPoolPayload {
  return {
    name: form.name.trim(),
    icon: form.icon.trim() || 'desktop',
    max_concurrent: Number(form.max_concurrent) || 1,
    auto_dispatch_enabled: form.auto_dispatch_enabled,
    dispatch_grace_seconds: Number(form.dispatch_grace_seconds) || 120,
    stale_timeout_seconds: Number(form.stale_timeout_seconds) || 120,
    idle_timeout_seconds: form.idle_timeout_seconds ? Number(form.idle_timeout_seconds) : null,
    is_active: form.is_active,
  }
}

function openCreate() {
  selectedPool.value = null
  fillForm(null)
  dialogOpen.value = true
}

function openEdit(pool: AdminPoolRecord) {
  selectedPool.value = pool
  fillForm(pool)
  dialogOpen.value = true
}

function closeDialog() {
  dialogOpen.value = false
  selectedPool.value = null
}

async function loadPools() {
  loading.value = true
  errorMessage.value = ''
  try {
    const response = await listAdminPools()
    pools.value = response.data
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '加载资源池失败'
    pools.value = []
  } finally {
    loading.value = false
  }
}

async function submitPool() {
  saving.value = true
  try {
    const payload = buildPayload()
    if (selectedPool.value) await updateAdminPool(selectedPool.value.id, payload)
    else await createAdminPool(payload)
    await loadPools()
    closeDialog()
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  void loadPools()
})
</script>

<style scoped>
@import './admin-ops.css';

.admin-pools__dialog {
  position: fixed;
  inset: 0;
  display: grid;
  place-items: center;
  background: rgba(15, 23, 42, 0.45);
  z-index: 20;
}

.admin-pools__panel {
  width: min(760px, calc(100vw - 32px));
  display: grid;
  gap: 16px;
  padding: 24px;
  border-radius: 18px;
  background: #fff;
}

.admin-pools__panel-header,
.admin-pools__panel-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.admin-pools__panel-header h2 {
  margin: 0;
}

.admin-pools__form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.admin-pools__form label {
  display: grid;
  gap: 6px;
}

.admin-pools__checkbox {
  display: flex !important;
  align-items: center;
  gap: 8px !important;
}

input {
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  padding: 9px 10px;
}
</style>
