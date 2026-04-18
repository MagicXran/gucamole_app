<template>
  <section class="sdk-version-panel">
    <p v-if="loading" class="sdk-version-panel__state">加载版本中...</p>
    <p v-else-if="errorMessage" class="sdk-version-panel__state sdk-version-panel__state--error">
      {{ errorMessage }}
    </p>
    <p v-else-if="!detail" class="sdk-version-panel__state">请选择 SDK 包查看版本。</p>

    <template v-else>
      <header class="sdk-version-panel__header">
        <div>
          <h2>{{ detail.name }}</h2>
          <p>{{ detail.summary || '暂无摘要' }}</p>
        </div>
        <a v-if="detail.homepage_url" :href="detail.homepage_url" target="_blank" rel="noopener">官网</a>
      </header>

      <section v-if="detail.versions.length === 0" class="sdk-version-panel__state">暂无版本</section>
      <article v-for="version in detail.versions" v-else :key="version.id" class="sdk-version-panel__version">
        <header>
          <h3>{{ version.version }}</h3>
          <span>{{ version.released_at || '未标注发布日期' }}</span>
        </header>
        <p>{{ version.release_notes || '暂无更新说明' }}</p>

        <ul class="sdk-version-panel__assets">
          <li v-for="asset in version.assets" :key="asset.id">
            <span>
              <strong>{{ asset.display_name }}</strong>
              <small>{{ asset.asset_kind }}</small>
            </span>
            <button
              :data-testid="`sdk-download-${asset.id}`"
              type="button"
              @click="$emit('download', asset.id)"
            >
              下载
            </button>
          </li>
        </ul>
      </article>
    </template>
  </section>
</template>

<script setup lang="ts">
import type { SdkPackageDetail } from '@/modules/sdk/types/sdk'

defineProps<{
  detail: SdkPackageDetail | null
  errorMessage: string
  loading: boolean
}>()

defineEmits<{
  download: [assetId: number]
}>()
</script>

<style scoped>
.sdk-version-panel {
  display: grid;
  gap: 16px;
}

.sdk-version-panel__header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

.sdk-version-panel__header h2,
.sdk-version-panel__header p,
.sdk-version-panel__version h3,
.sdk-version-panel__version p {
  margin: 0;
}

.sdk-version-panel__state {
  margin: 0;
  color: #475569;
}

.sdk-version-panel__state--error {
  color: #b91c1c;
}

.sdk-version-panel__version {
  display: grid;
  gap: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 16px;
}

.sdk-version-panel__version header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

.sdk-version-panel__assets {
  display: grid;
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.sdk-version-panel__assets li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.sdk-version-panel__assets span {
  display: grid;
  gap: 4px;
}

.sdk-version-panel__assets small {
  color: #64748b;
}

button,
a {
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  background: #fff;
  color: #1e3a8a;
  padding: 8px 12px;
  text-decoration: none;
  cursor: pointer;
}
</style>
