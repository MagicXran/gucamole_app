<template>
  <label class="filter-bar">
    <span>搜索</span>
    <input
      :value="modelValue"
      type="search"
      placeholder="按名称搜索"
      @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
    />
  </label>
</template>

<script setup lang="ts">
defineProps<{
  modelValue: string
}>()

defineEmits<{
  'update:modelValue': [value: string]
}>()
</script>

<style scoped>
.filter-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 18px 0;
  color: var(--portal-color-body);
  font-size: 14px;
}

input {
  width: min(360px, 100%);
  min-height: 44px;
  padding: 0 16px;
  border: 1px solid transparent;
  border-radius: 999px;
  background: var(--portal-color-surface-soft);
  color: var(--portal-color-ink);
  transition: border-color 0.2s ease, background 0.2s ease;
}

input:focus {
  outline: none;
  border-color: rgba(0, 82, 255, 0.22);
  background: var(--portal-color-surface);
}
</style>
