<template>
  <div v-if="open && catalog" class="vscode-policy-dialog">
    <div class="vscode-policy-dialog__panel">
      <header class="vscode-policy-dialog__header">
        <div>
          <h2>{{ initialProfile ? '编辑 VSCode 策略' : '新建 VSCode 策略' }}</h2>
          <p>全部权限开关默认允许，但程序、扩展、路径和网络白名单始终是锁定边界。</p>
        </div>
        <button type="button" @click="$emit('close')">关闭</button>
      </header>

      <p v-if="localError" class="vscode-policy-dialog__error">{{ localError }}</p>

      <section class="vscode-policy-dialog__section">
        <h3>基本信息</h3>
        <div class="vscode-policy-dialog__grid">
          <label><span>策略标识</span><input v-model="form.profile_key" data-testid="vscode-policy-key"></label>
          <label><span>显示名称</span><input v-model="form.display_name" data-testid="vscode-policy-name"></label>
          <label><span>策略版本</span><input :value="form.policy_version" disabled></label>
          <label class="vscode-policy-dialog__checkbox"><input v-model="form.is_active" type="checkbox" data-testid="vscode-policy-active"><span>启用策略</span></label>
          <label class="vscode-policy-dialog__wide"><span>说明</span><input v-model="form.description"></label>
          <label><span>user-data 根目录（锁定）</span><input v-model="form.user_data_root" disabled data-testid="vscode-policy-user-data-root"></label>
          <label><span>extensions 根目录（锁定）</span><input v-model="form.extensions_root" disabled data-testid="vscode-policy-extensions-root"></label>
          <label class="vscode-policy-dialog__wide"><span>默认工作区（锁定）</span><input v-model="form.default_workspace_template" disabled data-testid="vscode-policy-workspace"></label>
        </div>
      </section>

      <section class="vscode-policy-dialog__section">
        <div class="vscode-policy-dialog__section-header">
          <div>
            <h3>可授予权限</h3>
            <p>“全选”只允许所有已登记能力，不代表任意程序、扩展或网络。</p>
          </div>
          <div class="vscode-policy-dialog__toolbar">
            <button type="button" data-testid="vscode-policy-select-all" @click="selectAll">全选</button>
            <button type="button" data-testid="vscode-policy-clear-all" @click="clearAll">全不选</button>
            <button type="button" data-testid="vscode-policy-reset-defaults" @click="resetDefaults">恢复默认</button>
          </div>
        </div>
        <VscodePermissionMatrix
          :controls="catalog.controls"
          :permissions="form.permissions"
          @update:permissions="form.permissions = $event"
        />
      </section>

      <section class="vscode-policy-dialog__section">
        <h3>强制白名单</h3>
        <p v-if="missingAllowlistWarnings.length" class="vscode-policy-dialog__warning" data-testid="vscode-policy-invalid-warning">
          {{ missingAllowlistWarnings.join('；') }}
        </p>
        <div class="vscode-policy-dialog__allowlists">
          <VscodeAllowlistEditor v-model="form.allowed_shells" label="Shell" help="每行一个 Windows 可执行文件绝对路径。" test-id="vscode-policy-shells" />
          <VscodeAllowlistEditor v-model="form.allowed_tools" label="工具链" help="每行一个编译器、解释器、Git 或包管理器路径。" test-id="vscode-policy-tools" />
          <VscodeAllowlistEditor v-model="form.allowed_debuggers" label="调试器" help="每行一个允许的调试器路径。" test-id="vscode-policy-debuggers" />
          <VscodeAllowlistEditor v-model="form.allowed_extensions" label="扩展" help="每行一个 publisher.extension 标识。" test-id="vscode-policy-extensions" />
          <VscodeAllowlistEditor v-model="form.allowed_network_targets" label="网络目标" help="每行一个域名、URL 或 HOST:PORT。" test-id="vscode-policy-network-targets" />
        </div>
      </section>

      <section class="vscode-policy-dialog__section">
        <h3>已锁定安全基线</h3>
        <label v-for="item in catalog.locked_baseline" :key="item.code" class="vscode-policy-dialog__locked">
          <input type="checkbox" checked disabled>
          <span>{{ item.label }}</span>
        </label>
      </section>

      <section class="vscode-policy-dialog__section">
        <h3>最终生效预览</h3>
        <pre>{{ effectivePreview }}</pre>
      </section>

      <footer class="vscode-policy-dialog__actions">
        <button type="button" @click="$emit('close')">取消</button>
        <button type="button" data-testid="vscode-policy-submit" :disabled="saving" @click="submit">{{ saving ? '保存中...' : '保存' }}</button>
      </footer>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'

import VscodeAllowlistEditor from '@/modules/admin/components/VscodeAllowlistEditor.vue'
import VscodePermissionMatrix from '@/modules/admin/components/VscodePermissionMatrix.vue'
import type {
  VscodeControlCatalog,
  VscodeControlProfile,
  VscodeControlProfilePayload,
} from '@/modules/admin/types/vscodePolicies'

const props = defineProps<{
  open: boolean
  saving: boolean
  catalog: VscodeControlCatalog | null
  initialProfile: VscodeControlProfile | null
}>()

const emit = defineEmits<{
  close: []
  submit: [{ profileId: number | null; payload: VscodeControlProfilePayload }]
}>()

const form = reactive<VscodeControlProfilePayload>(emptyForm())
const localError = ref('')

function emptyForm(): VscodeControlProfilePayload {
  return {
    profile_key: '',
    display_name: '',
    description: '',
    policy_version: props.catalog?.policy_version || 1,
    is_active: false,
    permissions: { ...(props.catalog?.default_permissions || {}) },
    allowed_shells: [],
    allowed_tools: [],
    allowed_debuggers: [],
    allowed_extensions: [],
    allowed_network_targets: [],
    user_data_root: 'C:\\PortalProfiles',
    extensions_root: 'C:\\PortalExtensions',
    default_workspace_template: '\\\\tsclient\\{user_drive}',
  }
}

function hydrate() {
  const source = props.initialProfile
  Object.assign(form, emptyForm(), source ? {
    profile_key: source.profile_key,
    display_name: source.display_name,
    description: source.description,
    policy_version: source.policy_version,
    is_active: source.is_active,
    permissions: { ...source.permissions },
    allowed_shells: [...source.allowed_shells],
    allowed_tools: [...source.allowed_tools],
    allowed_debuggers: [...source.allowed_debuggers],
    allowed_extensions: [...source.allowed_extensions],
    allowed_network_targets: [...source.allowed_network_targets],
    user_data_root: source.user_data_root,
    extensions_root: source.extensions_root,
    default_workspace_template: source.default_workspace_template,
  } : {})
  localError.value = ''
}

watch(() => [props.open, props.initialProfile, props.catalog] as const, ([open]) => {
  if (open && props.catalog) hydrate()
}, { immediate: true })

const allowlistValues = computed<Record<string, string[]>>(() => ({
  allowed_shells: form.allowed_shells,
  allowed_tools: form.allowed_tools,
  allowed_debuggers: form.allowed_debuggers,
  allowed_extensions: form.allowed_extensions,
  allowed_network_targets: form.allowed_network_targets,
}))

const missingAllowlistWarnings = computed(() => {
  if (!props.catalog) return []
  const missing = new Map<string, string[]>()
  props.catalog.controls.forEach((control) => {
    if (!form.permissions[control.code]) return
    control.requires_allowlists.forEach((field) => {
      if ((allowlistValues.value[field] || []).length === 0) {
        missing.set(field, [...(missing.get(field) || []), control.label])
      }
    })
  })
  return [...missing.entries()].map(([field, labels]) => `${field} 为空：${labels.join('、')}`)
})

const effectivePreview = computed(() => JSON.stringify({
  valid: missingAllowlistWarnings.value.length === 0,
  guacamole: {
    disable_copy: !form.permissions.copy_remote_to_local,
    disable_paste: !form.permissions.paste_local_to_remote,
    disable_upload: !form.permissions.browser_upload,
    disable_download: !form.permissions.browser_download,
    enable_printing: Boolean(form.permissions.printing),
    enable_audio: Boolean(form.permissions.audio_output),
    enable_audio_input: Boolean(form.permissions.audio_input),
  },
  validation_errors: missingAllowlistWarnings.value,
}, null, 2))

function selectAll() {
  if (!props.catalog) return
  form.permissions = Object.fromEntries(props.catalog.controls.map((control) => [control.code, true]))
}

function clearAll() {
  if (!props.catalog) return
  form.permissions = Object.fromEntries(props.catalog.controls.map((control) => [control.code, false]))
}

function resetDefaults() {
  form.permissions = { ...(props.catalog?.default_permissions || {}) }
}

function submit() {
  localError.value = ''
  if (!form.profile_key.trim() || !form.display_name.trim()) {
    localError.value = '策略标识和显示名称为必填项'
    return
  }
  if (form.is_active && missingAllowlistWarnings.value.length) {
    localError.value = '启用策略前必须补齐所有必需白名单'
    return
  }
  emit('submit', {
    profileId: props.initialProfile?.id || null,
    payload: {
      ...form,
      profile_key: form.profile_key.trim(),
      display_name: form.display_name.trim(),
      description: form.description.trim(),
      permissions: { ...form.permissions },
      allowed_shells: [...form.allowed_shells],
      allowed_tools: [...form.allowed_tools],
      allowed_debuggers: [...form.allowed_debuggers],
      allowed_extensions: [...form.allowed_extensions],
      allowed_network_targets: [...form.allowed_network_targets],
    },
  })
}
</script>

<style scoped>
.vscode-policy-dialog {
  position: fixed;
  inset: 0;
  display: grid;
  place-items: center;
  z-index: 30;
  background: rgba(10, 11, 13, 0.55);
}

.vscode-policy-dialog__panel {
  width: min(1180px, calc(100vw - 32px));
  max-height: calc(100vh - 32px);
  overflow: auto;
  display: grid;
  gap: 16px;
  padding: 22px;
  border-radius: 24px;
  background: var(--portal-color-surface);
}

.vscode-policy-dialog__header,
.vscode-policy-dialog__section-header,
.vscode-policy-dialog__actions,
.vscode-policy-dialog__toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.vscode-policy-dialog__header h2,
.vscode-policy-dialog__header p,
.vscode-policy-dialog__section h3,
.vscode-policy-dialog__section p {
  margin: 0;
}

.vscode-policy-dialog__section {
  display: grid;
  gap: 12px;
  padding: 16px;
  border: 1px solid var(--portal-color-border);
  border-radius: 18px;
  background: var(--portal-color-page);
}

.vscode-policy-dialog__grid,
.vscode-policy-dialog__allowlists {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.vscode-policy-dialog__grid label {
  display: grid;
  gap: 6px;
}

.vscode-policy-dialog__wide {
  grid-column: 1 / -1;
}

.vscode-policy-dialog__checkbox,
.vscode-policy-dialog__locked {
  display: flex !important;
  align-items: center;
  gap: 8px !important;
}

.vscode-policy-dialog__error,
.vscode-policy-dialog__warning {
  padding: 10px 12px;
  border-radius: 14px;
  background: #fff7ed;
  color: var(--portal-color-warning);
}

input,
button {
  border: 1px solid var(--portal-color-border);
  border-radius: 14px;
  padding: 10px 12px;
  background: var(--portal-color-surface);
  color: var(--portal-color-ink);
}

button {
  cursor: pointer;
}

pre {
  overflow: auto;
  margin: 0;
  padding: 12px;
  border-radius: 14px;
  background: #111827;
  color: #d1fae5;
}

@media (max-width: 900px) {
  .vscode-policy-dialog__grid,
  .vscode-policy-dialog__allowlists {
    grid-template-columns: 1fr;
  }
}
</style>
