<template>
  <section class="attachment-editor">
    <article v-for="group in groups" :key="group.key" class="attachment-editor__group">
      <header class="attachment-editor__group-header">
        <h3>{{ group.title }}</h3>
        <button
          type="button"
          :data-testid="`attachment-add-${group.key}`"
          :disabled="disabled"
          @click="addItem(group.key)"
        >
          新增
        </button>
      </header>

      <div v-if="modelValue[group.key].length === 0" class="attachment-editor__empty">暂无附件</div>
      <div
        v-for="(item, index) in modelValue[group.key]"
        :key="`${group.key}-${index}`"
        class="attachment-editor__row"
      >
        <input
          :data-testid="`attachment-title-${group.key}-${index}`"
          :disabled="disabled"
          :value="item.title"
          placeholder="标题"
          @input="updateItem(group.key, index, 'title', $event)"
        >
        <input
          :data-testid="`attachment-summary-${group.key}-${index}`"
          :disabled="disabled"
          :value="item.summary"
          placeholder="摘要"
          @input="updateItem(group.key, index, 'summary', $event)"
        >
        <input
          :data-testid="`attachment-link-${group.key}-${index}`"
          :disabled="disabled"
          :value="item.link_url"
          placeholder="https://链接"
          @input="updateItem(group.key, index, 'link_url', $event)"
        >
        <button type="button" :disabled="disabled" @click="removeItem(group.key, index)">删除</button>
      </div>
    </article>
  </section>
</template>

<script setup lang="ts">
import type { AttachmentGroupKey, AttachmentItemDraft, PoolAttachments } from '@/modules/admin/types/apps'

const props = defineProps<{
  modelValue: PoolAttachments
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: PoolAttachments]
}>()

const groups = [
  { key: 'tutorial_docs', title: '教程文档' },
  { key: 'video_resources', title: '视频资源' },
  { key: 'plugin_downloads', title: '插件下载' },
] as const

function clonePayload(payload: PoolAttachments): PoolAttachments {
  return {
    pool_id: payload.pool_id,
    tutorial_docs: payload.tutorial_docs.map((item) => ({ ...item })),
    video_resources: payload.video_resources.map((item) => ({ ...item })),
    plugin_downloads: payload.plugin_downloads.map((item) => ({ ...item })),
  }
}

function normalizeGroup(items: AttachmentItemDraft[]) {
  return items.map((item, index) => ({
    ...item,
    sort_order: index,
  }))
}

function nextDraftItem(): AttachmentItemDraft {
  return {
    title: '',
    summary: '',
    link_url: '',
    sort_order: 0,
  }
}

function updateGroup(groupKey: AttachmentGroupKey, nextItems: AttachmentItemDraft[]) {
  const payload = clonePayload(props.modelValue)
  payload[groupKey] = normalizeGroup(nextItems)
  emit('update:modelValue', payload)
}

function addItem(groupKey: AttachmentGroupKey) {
  updateGroup(groupKey, [...props.modelValue[groupKey], nextDraftItem()])
}

function removeItem(groupKey: AttachmentGroupKey, index: number) {
  updateGroup(
    groupKey,
    props.modelValue[groupKey].filter((_, itemIndex) => itemIndex !== index),
  )
}

function updateItem(
  groupKey: AttachmentGroupKey,
  index: number,
  field: keyof AttachmentItemDraft,
  event: Event,
) {
  const target = event.target as HTMLInputElement
  const nextItems = props.modelValue[groupKey].map((item, itemIndex) => {
    if (itemIndex !== index) {
      return { ...item }
    }
    return {
      ...item,
      [field]: target.value,
    }
  })
  updateGroup(groupKey, nextItems)
}
</script>

<style scoped>
.attachment-editor {
  display: grid;
  gap: 16px;
}

.attachment-editor__group {
  display: grid;
  gap: 12px;
  padding: 14px;
  border: 1px solid #dbe4f0;
  border-radius: 12px;
  background: #f8fbff;
}

.attachment-editor__group-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.attachment-editor__group-header h3 {
  margin: 0;
}

.attachment-editor__row {
  display: grid;
  grid-template-columns: 1fr 1fr 2fr auto;
  gap: 8px;
}

.attachment-editor__empty {
  color: #64748b;
}

input,
button {
  border-radius: 10px;
}

input {
  border: 1px solid #cbd5e1;
  padding: 8px 10px;
}

button {
  border: 1px solid #cbd5e1;
  background: #fff;
  padding: 8px 10px;
  cursor: pointer;
}
</style>
