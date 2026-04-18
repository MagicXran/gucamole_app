<template>
  <div v-if="open" class="admin-app-dialog">
    <div class="admin-app-dialog__panel">
      <header class="admin-app-dialog__header">
        <h2>{{ mode === 'edit' ? '编辑应用' : '新建应用' }}</h2>
        <button type="button" @click="$emit('close')">关闭</button>
      </header>

      <div class="admin-app-dialog__grid">
        <label>
          <span>名称</span>
          <input v-model="form.name" data-testid="admin-app-name">
        </label>
        <label>
          <span>分类</span>
          <select v-model="form.app_kind" data-testid="admin-app-kind">
            <option value="commercial_software">商业软件</option>
            <option value="simulation_app">仿真APP</option>
            <option value="compute_tool">计算工具</option>
          </select>
        </label>
        <label>
          <span>主机</span>
          <input v-model="form.hostname" data-testid="admin-app-hostname">
        </label>
        <label>
          <span>端口</span>
          <input v-model.number="form.port" type="number">
        </label>
        <label>
          <span>RemoteApp</span>
          <input v-model="form.remote_app">
        </label>
        <label>
          <span>并发</span>
          <input v-model.number="form.member_max_concurrent" type="number" min="1">
        </label>
        <label>
          <span>资源池</span>
          <select v-model="form.pool_id" data-testid="admin-app-pool" @change="emitPoolChange">
            <option :value="null">未绑定</option>
            <option v-for="pool in pools" :key="pool.id" :value="pool.id">{{ pool.name }}</option>
          </select>
        </label>
        <label class="admin-app-dialog__checkbox">
          <input v-model="form.is_active" type="checkbox">
          <span>启用</span>
        </label>
      </div>

      <section class="admin-app-dialog__attachments">
        <header>
          <h3>资源池共享附件</h3>
          <p v-if="attachmentBindingWarning" class="admin-app-dialog__warning">{{ attachmentBindingWarning }}</p>
          <p v-if="attachmentsLoading">加载附件中...</p>
          <p v-else-if="!form.pool_id">先选择资源池，再维护附件。</p>
        </header>
        <AdminPoolAttachmentsEditor
          v-if="form.pool_id"
          :model-value="attachments"
          :disabled="saving"
          @update:model-value="$emit('update:attachments', $event)"
        />
      </section>

      <footer class="admin-app-dialog__actions">
        <button type="button" @click="$emit('close')">取消</button>
        <button type="button" data-testid="admin-app-submit" :disabled="saving" @click="handleSubmit">
          {{ saving ? '保存中...' : '保存' }}
        </button>
      </footer>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, watch } from 'vue'

import AdminPoolAttachmentsEditor from '@/modules/admin/components/AdminPoolAttachmentsEditor.vue'
import type { AdminAppFormPayload, AdminAppRecord, AdminPoolRecord, PoolAttachments } from '@/modules/admin/types/apps'

const props = defineProps<{
  open: boolean
  mode: 'create' | 'edit'
  saving: boolean
  pools: AdminPoolRecord[]
  initialApp: AdminAppRecord | null
  attachments: PoolAttachments
  attachmentsLoading: boolean
  attachmentBindingWarning: string
}>()

const emit = defineEmits<{
  close: []
  submit: [{ appId: number | null; payload: AdminAppFormPayload; attachments: PoolAttachments }]
  'pool-change': [poolId: number | null]
  'update:attachments': [value: PoolAttachments]
}>()

function defaultForm(): AdminAppFormPayload {
  return {
    name: '',
    icon: 'desktop',
    protocol: 'rdp',
    hostname: '',
    port: 3389,
    remote_app: '',
    pool_id: null,
    member_max_concurrent: 1,
    app_kind: 'commercial_software',
    ignore_cert: true,
    is_active: true,
  }
}

const form = reactive<AdminAppFormPayload>(defaultForm())

function hydrateForm(app: AdminAppRecord | null) {
  Object.assign(form, defaultForm(), {
    name: app?.name || '',
    icon: app?.icon || 'desktop',
    protocol: app?.protocol || 'rdp',
    hostname: app?.hostname || '',
    port: app?.port || 3389,
    remote_app: app?.remote_app || '',
    pool_id: app?.pool_id ?? null,
    member_max_concurrent: app?.member_max_concurrent || 1,
    app_kind: app?.app_kind || 'commercial_software',
    ignore_cert: true,
    is_active: app?.is_active ?? true,
  })
}

watch(
  () => [props.open, props.initialApp] as const,
  ([open]) => {
    if (!open) {
      return
    }
    hydrateForm(props.initialApp)
  },
  { immediate: true },
)

function cloneAttachments(payload: PoolAttachments): PoolAttachments {
  return {
    pool_id: payload.pool_id,
    tutorial_docs: payload.tutorial_docs.map((item) => ({ ...item })),
    video_resources: payload.video_resources.map((item) => ({ ...item })),
    plugin_downloads: payload.plugin_downloads.map((item) => ({ ...item })),
  }
}

function emitPoolChange() {
  emit('pool-change', form.pool_id)
}

function handleSubmit() {
  emit('submit', {
    appId: props.initialApp?.id ?? null,
    payload: {
      ...form,
      name: form.name.trim(),
      hostname: form.hostname.trim(),
      remote_app: form.remote_app.trim(),
      port: Number(form.port) || 3389,
      member_max_concurrent: Number(form.member_max_concurrent) || 1,
    },
    attachments: cloneAttachments(props.attachments),
  })
}
</script>

<style scoped>
.admin-app-dialog {
  position: fixed;
  inset: 0;
  display: grid;
  place-items: center;
  background: rgba(15, 23, 42, 0.45);
  z-index: 20;
}

.admin-app-dialog__panel {
  width: min(980px, calc(100vw - 32px));
  max-height: calc(100vh - 32px);
  overflow: auto;
  display: grid;
  gap: 18px;
  padding: 24px;
  border-radius: 18px;
  background: #fff;
}

.admin-app-dialog__header,
.admin-app-dialog__actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.admin-app-dialog__header h2,
.admin-app-dialog__attachments h3,
.admin-app-dialog__attachments p {
  margin: 0;
}

.admin-app-dialog__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.admin-app-dialog__grid label {
  display: grid;
  gap: 6px;
}

.admin-app-dialog__checkbox {
  align-self: end;
  display: flex !important;
  align-items: center;
}

.admin-app-dialog__attachments {
  display: grid;
  gap: 12px;
}

.admin-app-dialog__warning {
  padding: 10px 12px;
  border-radius: 10px;
  background: #fff7ed;
  color: #9a3412;
}

input,
select,
button {
  border-radius: 10px;
}

input,
select {
  border: 1px solid #cbd5e1;
  padding: 9px 10px;
}

button {
  border: 1px solid #cbd5e1;
  background: #fff;
  padding: 9px 12px;
  cursor: pointer;
}
</style>
