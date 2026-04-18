<template>
  <section class="sdk-package-list">
    <label class="sdk-package-list__search">
      <span>关键字</span>
      <input
        :value="keyword"
        type="search"
        placeholder="按 SDK 名称或摘要筛选"
        @input="$emit('update:keyword', ($event.target as HTMLInputElement).value)"
      />
    </label>

    <p v-if="loading" class="sdk-package-list__state">加载 SDK 中...</p>
    <p v-else-if="errorMessage" class="sdk-package-list__state sdk-package-list__state--error">
      {{ errorMessage }}
    </p>
    <p v-else-if="packages.length === 0" class="sdk-package-list__state">暂无匹配 SDK</p>

    <ul v-else class="sdk-package-list__items">
      <li v-for="item in packages" :key="item.id">
        <button
          type="button"
          :class="{ 'sdk-package-list__item--active': item.id === selectedPackageId }"
          @click="$emit('select', item.id)"
        >
          <strong>{{ item.name }}</strong>
          <span>{{ item.summary || '暂无摘要' }}</span>
        </button>
      </li>
    </ul>
  </section>
</template>

<script setup lang="ts">
import type { SdkPackageListItem } from '@/modules/sdk/types/sdk'

defineProps<{
  errorMessage: string
  keyword: string
  loading: boolean
  packages: SdkPackageListItem[]
  selectedPackageId: number | null
}>()

defineEmits<{
  select: [packageId: number]
  'update:keyword': [value: string]
}>()
</script>

<style scoped>
.sdk-package-list {
  display: grid;
  gap: 14px;
}

.sdk-package-list__search {
  display: grid;
  gap: 8px;
}

.sdk-package-list__search input {
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  padding: 10px 12px;
}

.sdk-package-list__state {
  margin: 0;
  color: #475569;
}

.sdk-package-list__state--error {
  color: #b91c1c;
}

.sdk-package-list__items {
  display: grid;
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.sdk-package-list__items button {
  display: grid;
  width: 100%;
  gap: 6px;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #fff;
  padding: 14px;
  text-align: left;
  cursor: pointer;
}

.sdk-package-list__item--active {
  border-color: #2563eb !important;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
}
</style>
