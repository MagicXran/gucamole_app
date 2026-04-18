<template>
  <section class="case-list-view">
    <header class="case-list-view__header">
      <div>
        <h1>任务案例</h1>
        <p>公共案例只读展示；想要自己动手，进详情再转存。</p>
      </div>
      <button type="button" @click="handleRefresh">刷新</button>
    </header>

    <label class="case-list-view__search">
      <span>关键字</span>
      <input v-model="casesStore.keyword" type="search" placeholder="按标题、摘要、案例编号筛选" />
    </label>

    <p v-if="casesStore.loading" class="case-list-view__state">加载案例中...</p>
    <p v-else-if="casesStore.errorMessage" class="case-list-view__state case-list-view__state--error">
      {{ casesStore.errorMessage }}
    </p>
    <p v-else-if="casesStore.filteredItems.length === 0" class="case-list-view__state">暂无匹配案例</p>

    <ul v-else class="case-list-view__list">
      <li v-for="item in casesStore.filteredItems" :key="item.id" class="case-list-view__item">
        <div class="case-list-view__meta">
          <h2>{{ item.title }}</h2>
          <p>{{ item.summary || '暂无摘要' }}</p>
          <dl>
            <div>
              <dt>案例编号</dt>
              <dd>{{ item.case_uid }}</dd>
            </div>
            <div>
              <dt>资产数</dt>
              <dd>{{ item.asset_count }}</dd>
            </div>
            <div>
              <dt>发布时间</dt>
              <dd>{{ item.published_at || '未发布' }}</dd>
            </div>
          </dl>
        </div>
        <button
          :data-testid="`case-detail-link-${item.id}`"
          type="button"
          @click="openDetail(item.id)"
        >
          查看详情
        </button>
      </li>
    </ul>
  </section>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'

import { useCasesStore } from '@/modules/cases/stores/cases'

const casesStore = useCasesStore()
const router = useRouter()

async function handleRefresh() {
  await casesStore.loadList(true)
}

async function openDetail(caseId: number) {
  await router.push(`/cases/${caseId}`)
}

onMounted(async () => {
  await casesStore.loadList()
})
</script>

<style scoped>
.case-list-view {
  display: grid;
  gap: 18px;
  padding: 24px;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
}

.case-list-view__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.case-list-view__search {
  display: grid;
  gap: 8px;
  max-width: 320px;
}

.case-list-view__search input {
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  padding: 10px 12px;
}

.case-list-view__state {
  margin: 0;
  color: #475569;
}

.case-list-view__state--error {
  color: #b91c1c;
}

.case-list-view__list {
  display: grid;
  gap: 16px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.case-list-view__item {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 18px;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
}

.case-list-view__meta {
  display: grid;
  gap: 10px;
}

.case-list-view__meta h2,
h1,
p,
dl,
dd {
  margin: 0;
}

.case-list-view__meta dl {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.case-list-view__meta dt {
  font-size: 12px;
  color: #64748b;
}

button {
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  background: #fff;
  color: #1e3a8a;
  padding: 8px 12px;
  cursor: pointer;
}
</style>
