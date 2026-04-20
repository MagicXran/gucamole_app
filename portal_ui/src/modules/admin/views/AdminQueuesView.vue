<template>
  <section class="admin-ops-view">
    <header class="admin-ops-view__header">
      <div>
        <h1>任务调度</h1>
        <p>排队明细、状态查看、取消排队。</p>
      </div>
      <button type="button" @click="queuesStore.loadQueues">刷新</button>
    </header>

    <div v-if="queuesStore.errorMessage" class="admin-ops-view__state admin-ops-view__state--error">
      {{ queuesStore.errorMessage }}
    </div>
    <div v-else-if="queuesStore.loading" class="admin-ops-view__state">加载排队中...</div>
    <table v-else class="admin-ops-view__table">
      <thead>
        <tr>
          <th>资源池</th>
          <th>用户</th>
          <th>状态</th>
          <th>创建时间</th>
          <th>Ready 到期</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="queuesStore.items.length === 0">
          <td colspan="6">当前无排队记录</td>
        </tr>
        <tr v-for="item in queuesStore.items" :key="item.queue_id">
          <td>{{ item.pool_name }}</td>
          <td>{{ item.display_name }}</td>
          <td>{{ item.status }}</td>
          <td>{{ item.created_at || '-' }}</td>
          <td>{{ item.ready_expires_at || item.cancel_reason || '-' }}</td>
          <td>
            <button type="button" :data-testid="`admin-queue-cancel-${item.queue_id}`" @click="queuesStore.cancelQueue(item.queue_id)">
              取消
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'

import { useAdminQueuesStore } from '@/modules/admin/stores/queues'

const queuesStore = useAdminQueuesStore()

onMounted(async () => {
  await queuesStore.loadQueues()
})
</script>

<style scoped>
.admin-ops-view {
  display: grid;
  gap: 18px;
  padding: 24px;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
}

.admin-ops-view__header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

.admin-ops-view__header h1,
.admin-ops-view__header p {
  margin: 0;
}

.admin-ops-view__table {
  width: 100%;
  border-collapse: collapse;
}

.admin-ops-view__table th,
.admin-ops-view__table td {
  padding: 10px 12px;
  border-bottom: 1px solid #e2e8f0;
  text-align: left;
}

.admin-ops-view__state {
  padding: 16px;
  border-radius: 12px;
  background: #f8fafc;
}

.admin-ops-view__state--error {
  background: #fef2f2;
  color: #b91c1c;
}

button {
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  background: #fff;
  padding: 8px 10px;
  cursor: pointer;
}
</style>
