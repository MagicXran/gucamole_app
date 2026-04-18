<template>
  <section class="admin-ops-view">
    <header class="admin-ops-view__header">
      <div>
        <h1>Worker状态</h1>
        <p>节点组、节点状态和软件能力是否就绪。</p>
      </div>
      <button type="button" @click="workersStore.loadWorkers">刷新</button>
    </header>

    <div v-if="workersStore.errorMessage" class="admin-ops-view__state admin-ops-view__state--error">
      {{ workersStore.errorMessage }}
    </div>
    <template v-else>
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
            <th>状态</th>
            <th>工作区</th>
            <th>软件就绪</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="workersStore.nodes.length === 0">
            <td colspan="5">暂无 Worker 节点</td>
          </tr>
          <tr v-for="node in workersStore.nodes" :key="node.id">
            <td>{{ node.display_name }} / {{ node.expected_hostname }}</td>
            <td>{{ node.group_name }}</td>
            <td>{{ node.status }}</td>
            <td>{{ node.workspace_share }} · {{ node.scratch_root }}</td>
            <td>{{ node.software_ready_count }}/{{ node.software_total_count }}</td>
          </tr>
        </tbody>
      </table>
    </template>
  </section>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'

import { useAdminWorkersStore } from '@/modules/admin/stores/workers'

const workersStore = useAdminWorkersStore()

onMounted(async () => {
  await workersStore.loadWorkers()
})
</script>

<style scoped>
@import './admin-ops.css';
</style>
