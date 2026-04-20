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
  color: #475569;
}

input {
  width: min(360px, 100%);
  padding: 10px 12px;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  color: #0f172a;
}
</style>
