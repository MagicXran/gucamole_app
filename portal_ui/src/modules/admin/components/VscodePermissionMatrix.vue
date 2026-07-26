<template>
  <div class="permission-matrix">
    <section v-for="group in groupedControls" :key="group.category" class="permission-matrix__group">
      <h4>{{ categoryLabel(group.category) }}</h4>
      <label v-for="control in group.items" :key="control.code" class="permission-matrix__item">
        <input
          type="checkbox"
          :checked="Boolean(permissions[control.code])"
          :data-testid="`vscode-control-${control.code}`"
          @change="setPermission(control.code, ($event.target as HTMLInputElement).checked)"
        >
        <span>
          <strong>{{ control.label }}</strong>
          <small>{{ control.enforcement }} · {{ control.risk }}</small>
        </span>
      </label>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import type { VscodeControlCatalogItem, VscodePermissionMap } from '@/modules/admin/types/vscodePolicies'

const props = defineProps<{
  controls: VscodeControlCatalogItem[]
  permissions: VscodePermissionMap
}>()

const emit = defineEmits<{
  'update:permissions': [VscodePermissionMap]
}>()

const groupedControls = computed(() => {
  const groups = new Map<string, VscodeControlCatalogItem[]>()
  props.controls.forEach((control) => {
    groups.set(control.category, [...(groups.get(control.category) || []), control])
  })
  return [...groups.entries()].map(([category, items]) => ({ category, items }))
})

function categoryLabel(category: string) {
  const labels: Record<string, string> = {
    workspace: '工作区',
    personalization: '个性化',
    execution: '执行',
    source_control: '源代码管理',
    packages: '包管理',
    extensions: '扩展',
    ai: 'AI',
    browser: '浏览器',
    remote: '远程开发',
    data_channel: '数据通道',
    device: '设备',
    network: '网络',
  }
  return labels[category] || category
}

function setPermission(code: string, value: boolean) {
  emit('update:permissions', { ...props.permissions, [code]: value })
}
</script>

<style scoped>
.permission-matrix {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.permission-matrix__group {
  display: grid;
  gap: 8px;
  padding: 14px;
  border: 1px solid var(--portal-color-border);
  border-radius: 16px;
  background: var(--portal-color-surface);
}

.permission-matrix__group h4 {
  margin: 0;
}

.permission-matrix__item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.permission-matrix__item span {
  display: grid;
  gap: 2px;
}

.permission-matrix__item small {
  color: var(--portal-color-muted);
}

@media (max-width: 900px) {
  .permission-matrix {
    grid-template-columns: 1fr;
  }
}
</style>
