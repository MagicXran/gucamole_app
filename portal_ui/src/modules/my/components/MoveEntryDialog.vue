<template>
  <div
    v-if="item"
    class="move-dialog-backdrop"
    @click.self="$emit('close')"
  >
    <section
      class="move-dialog"
      role="dialog"
      aria-modal="true"
      aria-labelledby="move-dialog-title"
      data-testid="move-dialog"
      tabindex="-1"
      @keydown.esc="$emit('close')"
    >
      <header class="move-dialog__header">
        <div>
          <p class="move-dialog__eyebrow">选择保存位置</p>
          <h2 id="move-dialog-title">移动 {{ item.name }}</h2>
        </div>
        <button
          ref="moveCancelButton"
          type="button"
          class="move-dialog__close"
          aria-label="关闭移动弹窗"
          @click="$emit('close')"
        >
          ×
        </button>
      </header>

      <div class="move-dialog__summary">
        <span>当前位置：{{ sourceDirectoryLabel }}</span>
        <span>目标位置：{{ targetPreview }}</span>
      </div>

      <div class="move-dialog__tree" aria-label="目录树">
        <div v-if="treeLoading" class="move-dialog__status">正在加载目录...</div>
        <div v-else-if="treeError" class="move-dialog__error">{{ treeError }}</div>
        <template v-else>
          <div
            v-for="node in visibleDirectoryNodes"
            :key="node.path || '__root__'"
            class="move-tree-row"
            :style="{ paddingLeft: `${node.depth * 18}px` }"
          >
            <button
              type="button"
              class="move-tree-row__target"
              :class="{ 'move-tree-row__target--active': selectedTargetPath === node.path }"
              :data-testid="`move-target-${node.path || 'root'}`"
              @click="selectMoveTarget(node)"
            >
              <span class="move-tree-row__name">{{ node.name }}</span>
              <span v-if="node.path === sourceDirectory" class="move-tree-row__tag">当前目录</span>
            </button>
            <button
              v-if="node.path || node.children.length > 0"
              type="button"
              class="move-tree-row__toggle"
              :aria-label="node.expanded ? `收起 ${node.name}` : `展开 ${node.name}`"
              @click="toggleDirectoryNode(node)"
            >
              {{ node.loading ? '加载中' : node.expanded ? '收起' : '展开' }}
            </button>
          </div>
        </template>
      </div>

      <p
        v-if="moveValidationMessage"
        class="move-dialog__error"
        data-testid="move-error"
      >
        {{ moveValidationMessage }}
      </p>

      <footer class="move-dialog__actions">
        <button type="button" @click="$emit('close')">取消</button>
        <button
          type="button"
          class="move-dialog__confirm"
          data-testid="move-confirm"
          :disabled="!canConfirmMove"
          @click="confirmMove"
        >
          移动到这里
        </button>
      </footer>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'

import type { MoveEntryPayload, WorkspaceFileItem } from '@/modules/my/types/files'

const props = defineProps<{
  item: WorkspaceFileItem | null
  currentPath: string
  directoryLoader: (path: string) => Promise<WorkspaceFileItem[]>
}>()

const emit = defineEmits<{
  close: []
  'move-entry': [payload: MoveEntryPayload]
}>()

type DirectoryNode = {
  name: string
  path: string
  depth: number
  children: DirectoryNode[]
  entries: WorkspaceFileItem[]
  loaded: boolean
  loading: boolean
  expanded: boolean
  errorMessage: string
}

const moveCancelButton = ref<HTMLButtonElement | null>(null)
const selectedTargetPath = ref<string | null>(null)
const moveValidationMessage = ref('')
const treeRoot = ref(createDirectoryNode('根目录', '', 0))
const treeLoading = ref(false)
const treeError = ref('')
const sourcePath = computed(() => props.item ? joinPath(props.currentPath, props.item.name) : '')
const sourceDirectory = computed(() => normalizePath(props.currentPath))
const sourceDirectoryLabel = computed(() => sourceDirectory.value || '根目录')
const targetPreview = computed(() => {
  if (!props.item || selectedTargetPath.value === null) {
    return '请选择目标文件夹'
  }
  return joinPath(selectedTargetPath.value, props.item.name) || props.item.name
})
const canConfirmMove = computed(() =>
  Boolean(props.item && selectedTargetPath.value !== null && !moveValidationMessage.value),
)
const visibleDirectoryNodes = computed(() => {
  const result: DirectoryNode[] = []

  function walk(node: DirectoryNode) {
    result.push(node)
    if (!node.expanded) {
      return
    }
    for (const child of node.children) {
      walk(child)
    }
  }

  walk(treeRoot.value)
  return result
})

watch(
  () => props.item,
  async (item) => {
    if (!item) {
      resetDialog()
      return
    }
    await openDialog()
  },
  { immediate: true },
)

function normalizePath(path: string) {
  return path.replace(/\\/g, '/').trim().replace(/^\/+/, '').replace(/\/+$/, '')
}

function joinPath(base: string, name: string) {
  const cleanedBase = normalizePath(base)
  const cleanedName = normalizePath(name)

  if (!cleanedBase) {
    return cleanedName
  }
  if (!cleanedName) {
    return cleanedBase
  }
  return `${cleanedBase}/${cleanedName}`
}

function createDirectoryNode(name: string, path: string, depth: number): DirectoryNode {
  return {
    name,
    path,
    depth,
    children: [],
    entries: [],
    loaded: false,
    loading: false,
    expanded: path === '',
    errorMessage: '',
  }
}

function entriesToDirectoryNodes(path: string, depth: number, entries: WorkspaceFileItem[]) {
  return entries
    .filter((entry) => entry.is_dir)
    .sort((left, right) => left.name.localeCompare(right.name, 'zh-Hans-CN'))
    .map((entry) => createDirectoryNode(entry.name, joinPath(path, entry.name), depth))
}

async function openDialog() {
  resetDialog()
  treeLoading.value = true
  moveValidationMessage.value = '请选择目标文件夹'
  await nextTick()
  moveCancelButton.value?.focus()

  await loadDirectoryNode(treeRoot.value)
  treeLoading.value = false
  if (treeRoot.value.errorMessage) {
    treeError.value = treeRoot.value.errorMessage
  }
}

function resetDialog() {
  treeRoot.value = createDirectoryNode('根目录', '', 0)
  selectedTargetPath.value = null
  moveValidationMessage.value = ''
  treeLoading.value = false
  treeError.value = ''
}

async function loadDirectoryNode(node: DirectoryNode) {
  if (node.loaded || node.loading) {
    return
  }

  node.loading = true
  node.errorMessage = ''
  try {
    const entries = await props.directoryLoader(node.path)
    node.entries = entries
    node.children = entriesToDirectoryNodes(node.path, node.depth + 1, entries)
    node.loaded = true
  } catch (error) {
    node.errorMessage = error instanceof Error ? error.message : '目录加载失败'
  } finally {
    node.loading = false
  }
}

async function toggleDirectoryNode(node: DirectoryNode) {
  await loadDirectoryNode(node)
  node.expanded = !node.expanded
  validateMoveTarget()
}

async function selectMoveTarget(node: DirectoryNode) {
  selectedTargetPath.value = node.path
  await loadDirectoryNode(node)
  validateMoveTarget()
}

function validateMoveTarget() {
  if (!props.item || selectedTargetPath.value === null) {
    moveValidationMessage.value = '请选择目标文件夹'
    return
  }

  const targetDirectory = normalizePath(selectedTargetPath.value)
  const targetPath = joinPath(targetDirectory, props.item.name)
  const selectedNode = visibleDirectoryNodes.value.find((node) => node.path === targetDirectory)

  if (targetDirectory === sourceDirectory.value) {
    moveValidationMessage.value = '文件已在当前目录中，无需移动'
    return
  }
  if (props.item.is_dir && (targetDirectory === sourcePath.value || targetDirectory.startsWith(`${sourcePath.value}/`))) {
    moveValidationMessage.value = '不能把文件夹移动到自身或子目录'
    return
  }
  if (sourcePath.value === normalizePath(targetPath)) {
    moveValidationMessage.value = '文件已在当前目录中，无需移动'
    return
  }
  if (selectedNode?.errorMessage) {
    moveValidationMessage.value = selectedNode.errorMessage
    return
  }
  if (selectedNode?.entries.some((entry) => entry.name === props.item?.name)) {
    moveValidationMessage.value = '目标目录已存在同名文件或文件夹'
    return
  }

  moveValidationMessage.value = ''
}

function confirmMove() {
  if (!props.item || selectedTargetPath.value === null) {
    validateMoveTarget()
    return
  }

  validateMoveTarget()
  if (moveValidationMessage.value) {
    return
  }

  emit('move-entry', {
    sourcePath: sourcePath.value,
    targetPath: joinPath(selectedTargetPath.value, props.item.name),
  })
}
</script>

<style scoped>
.move-dialog-backdrop {
  position: fixed;
  inset: 0;
  z-index: 40;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(15, 23, 42, 0.52);
  backdrop-filter: blur(4px);
}

.move-dialog {
  width: min(720px, 100%);
  max-height: min(760px, calc(100vh - 48px));
  display: grid;
  gap: 16px;
  overflow: hidden;
  padding: 22px;
  border: 1px solid #dbeafe;
  border-radius: 22px;
  background: #f8fafc;
  box-shadow: 0 24px 70px rgba(15, 23, 42, 0.28);
}

.move-dialog__header,
.move-dialog__summary,
.move-dialog__actions,
.move-tree-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.move-dialog__header,
.move-dialog__summary,
.move-dialog__actions {
  justify-content: space-between;
}

.move-dialog__eyebrow {
  margin: 0 0 4px;
  color: #2563eb;
  font-size: 13px;
  font-weight: 700;
}

.move-dialog h2 {
  margin: 0;
  color: #0f172a;
  font-size: 22px;
}

.move-dialog__close {
  width: 36px;
  height: 36px;
  padding: 0;
  border-radius: 999px;
  font-size: 24px;
  line-height: 1;
}

.move-dialog__summary {
  padding: 12px 14px;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  background: #fff;
  color: #475569;
  font-size: 14px;
}

.move-dialog__tree {
  min-height: 240px;
  max-height: 380px;
  overflow: auto;
  padding: 10px;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  background: #fff;
}

.move-tree-row {
  margin: 4px 0;
}

.move-tree-row__target {
  min-width: 0;
  flex: 1;
  justify-content: space-between;
  text-align: left;
}

.move-tree-row__target--active {
  border-color: #2563eb;
  background: #eff6ff;
}

.move-tree-row__name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.move-tree-row__tag {
  color: #b45309;
  font-size: 12px;
}

.move-tree-row__toggle {
  flex: none;
  padding: 7px 10px;
}

.move-dialog__status,
.move-dialog__error {
  padding: 12px 14px;
  border-radius: 12px;
}

.move-dialog__status {
  background: #eff6ff;
  color: #1e3a8a;
}

.move-dialog__error {
  background: #fef2f2;
  color: #b91c1c;
}

.move-dialog__actions {
  justify-content: flex-end;
}

.move-dialog__confirm {
  border-color: #1d4ed8;
  background: #2563eb;
  color: #fff;
}

.move-dialog__confirm:disabled {
  border-color: #cbd5e1;
  background: #e2e8f0;
  color: #64748b;
  cursor: not-allowed;
}

button {
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  background: #fff;
  color: #1e3a8a;
  padding: 8px 12px;
  cursor: pointer;
}

@media (max-width: 640px) {
  .move-dialog-backdrop {
    padding: 12px;
  }

  .move-dialog {
    max-height: calc(100vh - 24px);
    padding: 16px;
  }

  .move-dialog__summary {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
