<template>
  <label class="allowlist-editor">
    <span>{{ label }}</span>
    <textarea
      :value="modelValue.join('\n')"
      :data-testid="testId"
      rows="5"
      :placeholder="placeholder"
      @input="updateValue(($event.target as HTMLTextAreaElement).value)"
    />
    <small>{{ help }}</small>
  </label>
</template>

<script setup lang="ts">
defineProps<{
  modelValue: string[]
  label: string
  help: string
  testId: string
  placeholder?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [string[]]
}>()

function updateValue(value: string) {
  const seen = new Set<string>()
  const lines = value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter((item) => {
      const key = item.toLowerCase()
      if (!item || seen.has(key)) return false
      seen.add(key)
      return true
    })
  emit('update:modelValue', lines)
}
</script>

<style scoped>
.allowlist-editor {
  display: grid;
  gap: 6px;
}

textarea {
  resize: vertical;
  border: 1px solid var(--portal-color-border);
  border-radius: 14px;
  padding: 10px 12px;
  background: var(--portal-color-surface-soft);
  color: var(--portal-color-ink);
}

small {
  color: var(--portal-color-muted);
}
</style>
