<template>
  <section class="case-detail-view">
    <header class="case-detail-view__header">
      <div>
        <h1>{{ casesStore.detail?.title || '案例详情' }}</h1>
        <p>{{ casesStore.detail?.summary || '公共案例包详情与转存入口。' }}</p>
      </div>
      <div class="case-detail-view__actions">
        <button data-testid="case-download" type="button" :disabled="!caseId" @click="handleDownload">
          下载案例包
        </button>
        <button
          data-testid="case-transfer"
          type="button"
          :disabled="!casesStore.detail || casesStore.transferLoading"
          @click="handleTransfer"
        >
          {{ casesStore.transferLoading ? '转存中...' : '转存到个人空间' }}
        </button>
      </div>
    </header>

    <p v-if="casesStore.detailLoading" class="case-detail-view__state">加载详情中...</p>
    <p v-else-if="casesStore.detailErrorMessage" class="case-detail-view__state case-detail-view__state--error">
      {{ casesStore.detailErrorMessage }}
    </p>
    <template v-else-if="casesStore.detail">
      <dl class="case-detail-view__meta">
        <div>
          <dt>案例编号</dt>
          <dd>{{ casesStore.detail.case_uid }}</dd>
        </div>
        <div>
          <dt>发布时间</dt>
          <dd>{{ casesStore.detail.published_at || '未发布' }}</dd>
        </div>
        <div>
          <dt>资产数</dt>
          <dd>{{ casesStore.detail.asset_count }}</dd>
        </div>
      </dl>

      <section>
        <h2>Package Assets</h2>
        <ul class="case-detail-view__assets">
          <li v-for="asset in casesStore.detail.assets" :key="asset.id">
            <strong>{{ asset.display_name }}</strong>
            <span>{{ asset.package_relative_path }}</span>
          </li>
        </ul>
      </section>

      <p v-if="casesStore.transferResult" class="case-detail-view__transfer-result">
        已转存到：{{ casesStore.transferResult.target_path }}
      </p>

      <CommentThread :target-type="'case'" :target-id="casesStore.detail.id" />
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'

import CommentThread from '@/components/comments/CommentThread.vue'
import { useCasesStore } from '@/modules/cases/stores/cases'

const casesStore = useCasesStore()
const route = useRoute()
const caseId = computed(() => Number(route.params.caseId || 0))

function handleDownload() {
  if (!caseId.value) {
    return
  }
  window.open(`/api/cases/${caseId.value}/download`, '_blank', 'noopener')
}

async function handleTransfer() {
  await casesStore.transferCurrentCase()
}

async function loadCurrentCase() {
  if (!caseId.value) {
    casesStore.detailErrorMessage = '案例编号无效'
    return
  }
  await casesStore.openDetail(caseId.value)
}

watch(caseId, async (nextCaseId, previousCaseId) => {
  if (nextCaseId !== previousCaseId) {
    await loadCurrentCase()
  }
})

onMounted(async () => {
  await loadCurrentCase()
})
</script>

<style scoped>
.case-detail-view {
  display: grid;
  gap: 18px;
  padding: 24px;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
}

.case-detail-view__header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

.case-detail-view__actions {
  display: flex;
  gap: 12px;
}

.case-detail-view__state {
  margin: 0;
  color: #475569;
}

.case-detail-view__state--error {
  color: #b91c1c;
}

.case-detail-view__meta {
  display: flex;
  gap: 18px;
  flex-wrap: wrap;
  margin: 0;
}

.case-detail-view__meta dt {
  font-size: 12px;
  color: #64748b;
}

.case-detail-view__meta dd,
.case-detail-view__assets,
h1,
h2,
p {
  margin: 0;
}

.case-detail-view__assets {
  display: grid;
  gap: 12px;
  padding-left: 18px;
}

.case-detail-view__assets li {
  display: grid;
  gap: 4px;
}

.case-detail-view__transfer-result {
  color: #166534;
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
