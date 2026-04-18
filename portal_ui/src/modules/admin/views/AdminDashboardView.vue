<template>
  <section class="admin-dashboard">
    <header class="admin-dashboard__header">
      <div>
        <h1>系统管理工作台</h1>
        <p>先把运营最需要的三把刀接进 Vue：App管理、任务调度、资源监控。</p>
      </div>
    </header>

    <div class="admin-dashboard__grid">
      <RouterLink
        v-for="item in adminItems"
        :key="item.key"
        :to="item.path || '/admin'"
        class="admin-dashboard__card"
      >
        <h2>{{ item.title }}</h2>
        <p>{{ adminSummary(item.path) }}</p>
      </RouterLink>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'

import { useNavigationStore } from '@/stores/navigation'

const navigationStore = useNavigationStore()
const adminItems = computed(() => {
  return navigationStore.menuTree.find((group) => group.key === 'admin')?.children || []
})

function adminSummary(path?: string) {
  if (path === '/admin/analytics') {
    return '软件热度、案例活跃度、用户与部门排行。'
  }
  if (path === '/admin/apps') {
    return '应用配置、分类运营、池级附件。'
  }
  if (path === '/admin/queues') {
    return '排队明细、状态查看、取消排队。'
  }
  if (path === '/admin/monitor') {
    return '会话活跃度、资源占用、实时态势。'
  }
  if (path === '/admin/workers') {
    return '节点组、节点状态、执行侧健康度。'
  }
  return '系统管理入口。'
}
</script>

<style scoped>
.admin-dashboard {
  display: grid;
  gap: 18px;
  padding: 24px;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
}

.admin-dashboard__header h1,
.admin-dashboard__header p,
.admin-dashboard__card h2,
.admin-dashboard__card p {
  margin: 0;
}

.admin-dashboard__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
}

.admin-dashboard__card {
  display: grid;
  gap: 8px;
  padding: 18px;
  border: 1px solid #dbe4f0;
  border-radius: 14px;
  text-decoration: none;
  color: #0f172a;
  background: linear-gradient(180deg, #f8fbff 0%, #ffffff 100%);
}

.admin-dashboard__card:hover {
  border-color: #93c5fd;
  box-shadow: 0 8px 18px rgba(59, 130, 246, 0.12);
}
</style>
