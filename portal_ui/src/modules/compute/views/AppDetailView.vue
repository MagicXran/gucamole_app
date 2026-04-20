<template>
  <section class="app-detail">
    <RouterLink class="app-detail__back" :to="backPath">返回列表</RouterLink>

    <div v-if="computeStore.errorMessage" class="app-detail__error">{{ computeStore.errorMessage }}</div>
    <div v-else-if="isResolving" class="app-detail__loading">加载中...</div>
    <template v-else-if="app">
      <header class="app-detail__header">
        <div>
          <h1>{{ app.name }}</h1>
          <p>{{ app.protocol.toUpperCase() }} · 资源池 #{{ app.pool_id }}</p>
        </div>
        <div class="app-detail__header-actions">
          <button class="app-detail__launch" :disabled="launching" @click="handleLaunch">
            {{ launching ? '启动中...' : '启动应用' }}
          </button>
          <span class="app-detail__status">{{ app.has_capacity ? '可用' : '忙碌' }}</span>
        </div>
      </header>

      <dl class="app-detail__stats">
        <div>
          <dt>运行</dt>
          <dd>{{ app.active_count }}/{{ app.max_concurrent }}</dd>
        </div>
        <div>
          <dt>排队</dt>
          <dd>{{ app.queued_count }}</dd>
        </div>
        <div>
          <dt>脚本模式</dt>
          <dd>{{ app.supports_script ? app.script_status_label || '已配置' : '未配置' }}</dd>
        </div>
      </dl>

      <section class="app-detail__attachments">
        <div v-if="attachmentsLoading" class="app-detail__loading">附件加载中...</div>
        <div v-else-if="attachmentsError" class="app-detail__error">{{ attachmentsError }}</div>
        <template v-else>
          <div class="app-detail__attachment-group">
            <h2>教程文档</h2>
            <div v-if="attachments.tutorial_docs.length === 0" class="app-detail__empty">暂无教程文档</div>
            <a
              v-for="item in attachments.tutorial_docs"
              :key="item.id"
              class="app-detail__attachment-link"
              :href="item.link_url"
              target="_blank"
              rel="noreferrer"
            >
              <span>{{ item.title }}</span>
              <small v-if="item.summary" class="app-detail__attachment-summary">{{ item.summary }}</small>
            </a>
          </div>
          <div class="app-detail__attachment-group">
            <h2>视频资源</h2>
            <div v-if="attachments.video_resources.length === 0" class="app-detail__empty">暂无视频资源</div>
            <a
              v-for="item in attachments.video_resources"
              :key="item.id"
              class="app-detail__attachment-link"
              :href="item.link_url"
              target="_blank"
              rel="noreferrer"
            >
              <span>{{ item.title }}</span>
              <small v-if="item.summary" class="app-detail__attachment-summary">{{ item.summary }}</small>
            </a>
          </div>
          <div class="app-detail__attachment-group">
            <h2>插件下载</h2>
            <div v-if="attachments.plugin_downloads.length === 0" class="app-detail__empty">暂无插件下载</div>
            <a
              v-for="item in attachments.plugin_downloads"
              :key="item.id"
              class="app-detail__attachment-link"
              :href="item.link_url"
              target="_blank"
              rel="noreferrer"
            >
              <span>{{ item.title }}</span>
              <small v-if="item.summary" class="app-detail__attachment-summary">{{ item.summary }}</small>
            </a>
          </div>
        </template>
      </section>

      <section class="app-detail__related-cases">
        <h2>相关案例</h2>
        <div v-if="relatedCasesLoading" class="app-detail__loading">相关案例加载中...</div>
        <div v-else-if="relatedCases.length === 0" class="app-detail__empty">暂无相关案例</div>
        <RouterLink
          v-for="item in relatedCases"
          :key="item.id"
          :to="`/cases/${item.id}`"
          class="app-detail__related-case-link"
          :data-testid="`related-case-link-${item.id}`"
        >
          <span>{{ item.title }}</span>
          <small v-if="item.summary" class="app-detail__attachment-summary">{{ item.summary }}</small>
        </RouterLink>
      </section>

      <CommentThread :target-type="'app'" :target-id="app.id" />
    </template>
    <div v-else class="app-detail__missing">应用不存在</div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import CommentThread from '@/components/comments/CommentThread.vue'
import { getCaseList } from '@/modules/cases/services/api/cases'
import type { CaseListItem } from '@/modules/cases/types/cases'
import { getPoolAttachments } from '@/services/api/compute'
import { useComputeStore } from '@/stores/compute'
import type { AppAttachmentItem, PoolAttachmentResponse } from '@/types/compute'

const route = useRoute()
const computeStore = useComputeStore()

const emptyAttachments = (poolId: number): PoolAttachmentResponse => ({
  pool_id: poolId,
  tutorial_docs: [],
  video_resources: [],
  plugin_downloads: [],
})

const poolId = computed(() => Number(route.params.poolId))
const app = computed(() => computeStore.getAppByPoolId(poolId.value))
const isResolving = computed(() => computeStore.loading || (!computeStore.loaded && computeStore.apps.length === 0 && !computeStore.errorMessage))
const backPath = computed(() => {
  if (app.value?.app_kind === 'simulation_app') return '/compute/simulation'
  if (app.value?.app_kind === 'compute_tool') return '/compute/tools'
  return '/compute/commercial'
})

const attachmentsData = ref<PoolAttachmentResponse>(emptyAttachments(poolId.value))
const attachmentsLoading = ref(false)
const attachmentsError = ref('')
const attachmentsLoaded = ref(false)
const attachmentRequestToken = ref(0)
const launching = ref(false)
const relatedCasesData = ref<CaseListItem[]>([])
const relatedCasesLoading = ref(false)
const relatedCasesRequestToken = ref(0)

function toSafeLinkUrl(linkUrl: string): string | null {
  const normalized = linkUrl.trim()
  if (!/^https?:\/\//i.test(normalized)) {
    return null
  }
  try {
    const parsed = new URL(normalized)
    return parsed.protocol === 'http:' || parsed.protocol === 'https:' ? parsed.toString() : null
  } catch {
    return null
  }
}

function filterSafeAttachmentItems(items: AppAttachmentItem[]): AppAttachmentItem[] {
  return items.flatMap((item) => {
    const safeLinkUrl = toSafeLinkUrl(item.link_url)
    if (!safeLinkUrl) {
      return []
    }
    return [{ ...item, link_url: safeLinkUrl }]
  })
}

function sanitizeAttachments(payload: PoolAttachmentResponse): PoolAttachmentResponse {
  return {
    pool_id: payload.pool_id,
    tutorial_docs: filterSafeAttachmentItems(payload.tutorial_docs),
    video_resources: filterSafeAttachmentItems(payload.video_resources),
    plugin_downloads: filterSafeAttachmentItems(payload.plugin_downloads),
  }
}

const attachments = computed(() => sanitizeAttachments(attachmentsData.value))
const relatedCases = computed(() =>
  relatedCasesData.value
    .filter((item) => item.app_id === app.value?.id)
    .slice(0, 3),
)

async function ensureAppAndAttachments() {
  if (computeStore.apps.length === 0) {
    await computeStore.loadApps()
  }
  if (app.value) {
    await Promise.all([loadAttachments(), loadRelatedCases()])
  } else if (computeStore.loaded) {
    attachmentsData.value = emptyAttachments(poolId.value)
    attachmentsLoaded.value = true
    attachmentsLoading.value = false
    attachmentsError.value = ''
    relatedCasesData.value = []
    relatedCasesLoading.value = false
  }
}

onMounted(() => {
  void ensureAppAndAttachments()
})

watch(poolId, () => {
  attachmentsData.value = emptyAttachments(poolId.value)
  attachmentsLoaded.value = false
  attachmentsLoading.value = false
  attachmentsError.value = ''
  relatedCasesData.value = []
  relatedCasesLoading.value = false
  void ensureAppAndAttachments()
})

async function loadAttachments() {
  const requestToken = attachmentRequestToken.value + 1
  attachmentRequestToken.value = requestToken
  attachmentsLoading.value = true
  attachmentsLoaded.value = false
  attachmentsError.value = ''
  try {
    const response = await getPoolAttachments(poolId.value)
    if (requestToken !== attachmentRequestToken.value) {
      return
    }
    attachmentsData.value = response.data
  } catch (error) {
    if (requestToken !== attachmentRequestToken.value) {
      return
    }
    attachmentsData.value = emptyAttachments(poolId.value)
    attachmentsError.value = error instanceof Error ? error.message : '附件加载失败'
  } finally {
    if (requestToken !== attachmentRequestToken.value) {
      return
    }
    attachmentsLoaded.value = true
    attachmentsLoading.value = false
  }
}

async function loadRelatedCases() {
  const requestToken = relatedCasesRequestToken.value + 1
  relatedCasesRequestToken.value = requestToken
  relatedCasesLoading.value = true
  try {
    const response = await getCaseList()
    if (requestToken !== relatedCasesRequestToken.value) {
      return
    }
    relatedCasesData.value = response.data
  } catch {
    if (requestToken !== relatedCasesRequestToken.value) {
      return
    }
    relatedCasesData.value = []
  } finally {
    if (requestToken !== relatedCasesRequestToken.value) {
      return
    }
    relatedCasesLoading.value = false
  }
}

async function handleLaunch() {
  if (!app.value || launching.value) {
    return
  }
  launching.value = true
  try {
    const { launchRemoteApp } = await import('@/modules/compute/services/launch')
    await launchRemoteApp(app.value.id, app.value.name, app.value.pool_id || 0)
  } finally {
    launching.value = false
  }
}
</script>

<style scoped>
.app-detail {
  display: grid;
  gap: 20px;
  padding: 24px;
  border-radius: 16px;
  background: #fff;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
}

.app-detail__back {
  width: fit-content;
  color: #1d4ed8;
  text-decoration: none;
  font-weight: 600;
}

.app-detail__header {
  display: flex;
  justify-content: space-between;
  gap: 24px;
}

.app-detail__header-actions {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

h1 {
  margin: 0 0 8px;
  font-size: 32px;
  color: #0f172a;
}

p {
  margin: 0;
  color: #64748b;
}

.app-detail__status {
  align-self: start;
  padding: 6px 12px;
  border-radius: 999px;
  color: #166534;
  background: #dcfce7;
}

.app-detail__launch {
  border: 1px solid #bfdbfe;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  cursor: pointer;
  font-weight: 600;
  padding: 8px 14px;
}

.app-detail__stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin: 0;
}

.app-detail__stats div {
  padding: 14px;
  border-radius: 12px;
  background: #f8fafc;
}

dt {
  color: #64748b;
  font-size: 13px;
}

dd {
  margin: 6px 0 0;
  color: #0f172a;
  font-weight: 700;
}

.app-detail__attachments {
  display: grid;
  gap: 18px;
}

.app-detail__related-cases {
  display: grid;
  gap: 10px;
  padding: 16px;
  border-radius: 14px;
  background: #f8fafc;
}

.app-detail__related-cases h2 {
  margin: 0;
  font-size: 18px;
  color: #1e3a8a;
}

.app-detail__attachment-group {
  display: grid;
  gap: 10px;
  padding: 16px;
  border-radius: 14px;
  background: #f8fafc;
}

.app-detail__attachment-group h2 {
  margin: 0;
  font-size: 18px;
  color: #1e3a8a;
}

.app-detail__attachment-link {
  display: grid;
  gap: 4px;
  color: #1d4ed8;
  text-decoration: none;
  font-weight: 600;
}

.app-detail__related-case-link {
  display: grid;
  gap: 4px;
  color: #1d4ed8;
  text-decoration: none;
  font-weight: 600;
}

.app-detail__attachment-summary {
  color: #64748b;
  font-size: 13px;
  font-weight: 400;
}

.app-detail__empty {
  color: #64748b;
}

.app-detail__missing {
  color: #b91c1c;
}

.app-detail__loading {
  color: #475569;
}

.app-detail__error {
  color: #b91c1c;
}
</style>
