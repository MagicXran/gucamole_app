<template>
  <section class="admin-analytics">
    <header class="admin-analytics__header">
      <div>
        <h1>统计看板</h1>
        <p>给运营和管理员一个能直接盯住使用热度的台面，不上图表库，少一点噪音。</p>
      </div>
    </header>

    <p v-if="loading" class="admin-analytics__state">统计数据加载中...</p>
    <p v-else-if="errorMessage" class="admin-analytics__state admin-analytics__state--error">
      {{ errorMessage }}
    </p>

    <template v-else-if="overview">
      <div class="admin-analytics__cards">
        <article v-for="card in cards" :key="card.key" class="admin-analytics__card">
          <span class="admin-analytics__card-label">{{ card.label }}</span>
          <strong class="admin-analytics__card-value">{{ card.value }}</strong>
        </article>
      </div>

      <div class="admin-analytics__sections">
        <section class="admin-analytics__panel">
          <header class="admin-analytics__panel-header">
            <h2>软件启动排行</h2>
            <span>按启动次数</span>
          </header>
          <table class="admin-analytics__table">
            <thead>
              <tr>
                <th>软件</th>
                <th>启动次数</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in overview.software_ranking" :key="item.app_id">
                <td>{{ item.app_name }}</td>
                <td>{{ item.launch_count }}</td>
              </tr>
            </tbody>
          </table>
        </section>

        <section class="admin-analytics__panel">
          <header class="admin-analytics__panel-header">
            <h2>项目案例排行</h2>
            <span>按总事件数</span>
          </header>
          <table class="admin-analytics__table">
            <thead>
              <tr>
                <th>案例</th>
                <th>详情</th>
                <th>下载</th>
                <th>转交</th>
                <th>总事件</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in overview.case_ranking" :key="item.case_id">
                <td>
                  <strong>{{ item.case_title }}</strong>
                  <div class="admin-analytics__subtext">{{ item.case_uid }}</div>
                </td>
                <td>{{ item.detail_count }}</td>
                <td>{{ item.download_count }}</td>
                <td>{{ item.transfer_count }}</td>
                <td>{{ item.event_count }}</td>
              </tr>
            </tbody>
          </table>
        </section>

        <section class="admin-analytics__panel">
          <header class="admin-analytics__panel-header">
            <h2>用户活跃排行</h2>
            <span>按总事件数</span>
          </header>
          <table class="admin-analytics__table">
            <thead>
              <tr>
                <th>用户</th>
                <th>部门</th>
                <th>软件启动</th>
                <th>案例事件</th>
                <th>总事件</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in overview.user_ranking" :key="item.user_id">
                <td>
                  <strong>{{ item.display_name }}</strong>
                  <div class="admin-analytics__subtext">{{ item.username }}</div>
                </td>
                <td>{{ item.department }}</td>
                <td>{{ item.software_launch_count }}</td>
                <td>{{ item.case_event_count }}</td>
                <td>{{ item.event_count }}</td>
              </tr>
            </tbody>
          </table>
        </section>

        <section class="admin-analytics__panel">
          <header class="admin-analytics__panel-header">
            <h2>部门活跃排行</h2>
            <span>按总事件数</span>
          </header>
          <table class="admin-analytics__table">
            <thead>
              <tr>
                <th>部门</th>
                <th>活跃用户</th>
                <th>总事件</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in overview.department_ranking" :key="item.department">
                <td>{{ item.department }}</td>
                <td>{{ item.user_count }}</td>
                <td>{{ item.event_count }}</td>
              </tr>
            </tbody>
          </table>
        </section>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { storeToRefs } from 'pinia'

import { useAdminAnalyticsStore } from '@/modules/admin/stores/analytics'

const analyticsStore = useAdminAnalyticsStore()
const { overview, loading, errorMessage } = storeToRefs(analyticsStore)

const cards = computed(() => {
  const totals = overview.value?.overview
  if (!totals) {
    return []
  }

  return [
    { key: 'software_launches', label: '软件启动次数', value: totals.software_launches },
    { key: 'case_events', label: '案例事件次数', value: totals.case_events },
    { key: 'active_users', label: '活跃用户数', value: totals.active_users },
    { key: 'department_count', label: '活跃部门数', value: totals.department_count },
  ]
})

onMounted(() => {
  analyticsStore.loadOverview()
})
</script>

<style scoped>
.admin-analytics {
  display: grid;
  gap: 18px;
  padding: 24px;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
}

.admin-analytics__header h1,
.admin-analytics__header p,
.admin-analytics__panel-header h2,
.admin-analytics__panel-header span {
  margin: 0;
}

.admin-analytics__cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
}

.admin-analytics__card,
.admin-analytics__panel {
  border: 1px solid #dbe4f0;
  border-radius: 14px;
  background: #fff;
}

.admin-analytics__card {
  display: grid;
  gap: 8px;
  padding: 18px;
  background: linear-gradient(180deg, #f8fbff 0%, #ffffff 100%);
}

.admin-analytics__card-label {
  color: #475569;
  font-size: 14px;
}

.admin-analytics__card-value {
  font-size: 28px;
  line-height: 1;
  color: #0f172a;
}

.admin-analytics__sections {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 16px;
}

.admin-analytics__panel {
  overflow: hidden;
}

.admin-analytics__panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 16px 18px;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
}

.admin-analytics__panel-header span,
.admin-analytics__subtext,
.admin-analytics__state {
  color: #64748b;
  font-size: 13px;
}

.admin-analytics__state {
  margin: 0;
}

.admin-analytics__state--error {
  color: #b91c1c;
}

.admin-analytics__table {
  width: 100%;
  border-collapse: collapse;
}

.admin-analytics__table th,
.admin-analytics__table td {
  padding: 12px 16px;
  border-bottom: 1px solid #e2e8f0;
  text-align: left;
  vertical-align: top;
}

.admin-analytics__table th {
  font-size: 13px;
  font-weight: 600;
  color: #475569;
  background: #fff;
}

.admin-analytics__table tbody tr:last-child td {
  border-bottom: none;
}
</style>
