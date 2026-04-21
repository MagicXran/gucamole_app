<template>
  <div v-if="open" class="admin-app-dialog">
    <div class="admin-app-dialog__panel">
      <header class="admin-app-dialog__header">
        <div>
          <h2>{{ mode === 'edit' ? '编辑应用' : '新建应用' }}</h2>
          <p>按旧后台完整参数来，别再把 RDP 配置剁成半截。</p>
        </div>
        <button type="button" @click="$emit('close')">关闭</button>
      </header>

      <p v-if="localError" class="admin-app-dialog__warning">{{ localError }}</p>

      <section class="admin-app-dialog__section">
        <h3>基础信息</h3>
        <div class="admin-app-dialog__grid">
          <label><span>名称</span><input v-model="form.name" data-testid="admin-app-name"></label>
          <label>
            <span>分类</span>
            <select v-model="form.app_kind" data-testid="admin-app-kind">
              <option value="commercial_software">商业软件</option>
              <option value="simulation_app">仿真APP</option>
              <option value="compute_tool">计算工具</option>
            </select>
          </label>
          <label><span>图标</span><input v-model="form.icon" data-testid="admin-app-icon"></label>
          <label>
            <span>协议</span>
            <select v-model="form.protocol" data-testid="admin-app-protocol">
              <option value="rdp">RDP</option>
            </select>
          </label>
          <label><span>主机</span><input v-model="form.hostname" data-testid="admin-app-hostname"></label>
          <label><span>端口</span><input v-model.number="form.port" type="number" min="1" max="65535" data-testid="admin-app-port"></label>
          <label>
            <span>资源池</span>
            <select v-model="form.pool_id" data-testid="admin-app-pool" @change="emitPoolChange">
              <option :value="null">未绑定</option>
              <option v-for="pool in pools" :key="pool.id" :value="pool.id">{{ pool.name }}</option>
            </select>
          </label>
          <label><span>成员并发上限</span><input v-model.number="form.member_max_concurrent" type="number" min="1" data-testid="admin-app-member-max"></label>
          <label class="admin-app-dialog__checkbox">
            <input v-model="form.is_active" type="checkbox" data-testid="admin-app-active">
            <span>启用</span>
          </label>
        </div>
      </section>

      <section class="admin-app-dialog__section">
        <h3>连接认证</h3>
        <div class="admin-app-dialog__grid">
          <label><span>RDP 用户名</span><input v-model="form.rdp_username" data-testid="admin-app-rdp-username"></label>
          <label><span>RDP 密码</span><input v-model="form.rdp_password" type="password" autocomplete="new-password" data-testid="admin-app-rdp-password"></label>
          <label><span>域名</span><input v-model="form.domain" data-testid="admin-app-domain"></label>
          <label>
            <span>安全模式</span>
            <select v-model="form.security" data-testid="admin-app-security">
              <option value="nla">nla</option>
              <option value="tls">tls</option>
              <option value="rdp">rdp</option>
              <option value="any">any</option>
            </select>
          </label>
          <label class="admin-app-dialog__checkbox">
            <input v-model="form.ignore_cert" type="checkbox" data-testid="admin-app-ignore-cert">
            <span>忽略证书错误</span>
          </label>
        </div>
      </section>

      <section class="admin-app-dialog__section">
        <h3>RemoteApp 启动</h3>
        <div class="admin-app-dialog__grid">
          <label><span>RemoteApp</span><input v-model="form.remote_app" placeholder="如 ||notepad" data-testid="admin-app-remote-app"></label>
          <label><span>工作目录</span><input v-model="form.remote_app_dir" data-testid="admin-app-remote-dir"></label>
          <label class="admin-app-dialog__wide"><span>命令参数</span><input v-model="form.remote_app_args" data-testid="admin-app-remote-args"></label>
        </div>
      </section>

      <details class="admin-app-dialog__details" :open="form.script_enabled">
        <summary>脚本模式</summary>
        <div class="admin-app-dialog__details-body">
          <p class="admin-app-dialog__hint">普通 RemoteApp 不需要脚本；启用后必须选执行器和 Worker 组。</p>
          <label class="admin-app-dialog__checkbox">
            <input v-model="form.script_enabled" type="checkbox" data-testid="admin-app-script-enabled">
            <span>启用脚本模式</span>
          </label>
          <div class="admin-app-dialog__grid">
            <label>
              <span>软件预设</span>
              <select v-model="form.script_profile_key" data-testid="admin-app-script-profile" @change="applySelectedScriptProfile">
                <option :value="null">未选择</option>
                <option v-for="profile in scriptProfiles" :key="profile.profile_key" :value="profile.profile_key">{{ profile.display_name }}</option>
              </select>
            </label>
            <label>
              <span>脚本执行器</span>
              <select v-model="form.script_executor_key" data-testid="admin-app-script-executor">
                <option :value="null">未选择</option>
                <option value="python_api">python_api</option>
                <option value="command_statusfile">command_statusfile</option>
              </select>
            </label>
            <label>
              <span>脚本 Worker 组</span>
              <select v-model="form.script_worker_group_id" data-testid="admin-app-script-worker-group">
                <option :value="null">未选择</option>
                <option v-for="group in workerGroups" :key="group.id" :value="group.id">{{ group.name }}</option>
              </select>
            </label>
            <label><span>脚本 scratch 根目录</span><input v-model="form.script_scratch_root" placeholder="留空使用节点默认" data-testid="admin-app-script-scratch-root"></label>
            <label><span>Python 解释器路径</span><input v-model="form.script_python_executable" placeholder="留空使用 Worker 默认 Python" data-testid="admin-app-script-python-executable"></label>
            <label><span>额外环境 JSON</span><input v-model="scriptPythonEnvText" placeholder='如 {"LICENSE_SERVER":"1.2.3.4"}' data-testid="admin-app-script-python-env"></label>
          </div>
          <div class="admin-app-dialog__preview"><strong>预设说明：</strong>{{ scriptProfileHint }}</div>
          <div class="admin-app-dialog__preview">{{ scriptBindingSummary }}</div>
        </div>
      </details>

      <details class="admin-app-dialog__details">
        <summary>高级 RDP 参数</summary>
        <div class="admin-app-dialog__details-body">
          <section class="admin-app-dialog__subsection">
            <h4>显示与性能</h4>
            <div class="admin-app-dialog__grid">
              <label>
                <span>色深</span>
                <select v-model="form.color_depth" data-testid="admin-app-color-depth">
                  <option :value="null">自动</option>
                  <option :value="8">8 位 (256色)</option>
                  <option :value="16">16 位 (高彩)</option>
                  <option :value="24">24 位 (真彩)</option>
                </select>
              </label>
              <label>
                <span>缩放模式</span>
                <select v-model="form.resize_method" data-testid="admin-app-resize-method">
                  <option value="display-update">display-update</option>
                  <option value="reconnect">reconnect</option>
                </select>
              </label>
              <label class="admin-app-dialog__checkbox"><input v-model="form.disable_gfx" type="checkbox" data-testid="admin-app-disable-gfx"><span>禁用 GFX Pipeline（推荐）</span></label>
              <label class="admin-app-dialog__checkbox"><input v-model="form.enable_wallpaper" type="checkbox" data-testid="admin-app-enable-wallpaper"><span>显示桌面壁纸</span></label>
              <label class="admin-app-dialog__checkbox"><input v-model="form.enable_font_smoothing" type="checkbox" data-testid="admin-app-enable-font-smoothing"><span>字体平滑 (ClearType)</span></label>
            </div>
          </section>

          <section class="admin-app-dialog__subsection">
            <h4>安全与剪贴板</h4>
            <div class="admin-app-dialog__grid">
              <label class="admin-app-dialog__checkbox"><input v-model="form.disable_copy" type="checkbox" data-testid="admin-app-disable-copy"><span>禁止远程 → 本地复制</span></label>
              <label class="admin-app-dialog__checkbox"><input v-model="form.disable_paste" type="checkbox" data-testid="admin-app-disable-paste"><span>禁止本地 → 远程粘贴</span></label>
            </div>
          </section>

          <section class="admin-app-dialog__subsection">
            <h4>文件传输通道</h4>
            <div class="admin-app-dialog__grid">
              <label>
                <span>浏览器下载通道</span>
                <select v-model="form.disable_download" data-testid="admin-app-disable-download">
                  <option :value="null">继承全局</option>
                  <option :value="1">强制禁用</option>
                  <option :value="0">强制允许</option>
                </select>
              </label>
              <label>
                <span>浏览器上传通道</span>
                <select v-model="form.disable_upload" data-testid="admin-app-disable-upload">
                  <option :value="null">继承全局</option>
                  <option :value="1">强制禁用</option>
                  <option :value="0">强制允许</option>
                </select>
              </label>
            </div>
            <p class="admin-app-dialog__hint">继承全局=跟随系统配置；强制允许会覆盖全局禁用。</p>
          </section>

          <section class="admin-app-dialog__subsection">
            <h4>音频与设备</h4>
            <div class="admin-app-dialog__grid">
              <label class="admin-app-dialog__checkbox"><input v-model="form.enable_audio" type="checkbox" data-testid="admin-app-enable-audio"><span>音频输出</span></label>
              <label class="admin-app-dialog__checkbox"><input v-model="form.enable_audio_input" type="checkbox" data-testid="admin-app-enable-audio-input"><span>麦克风输入</span></label>
              <label class="admin-app-dialog__checkbox"><input v-model="form.enable_printing" type="checkbox" data-testid="admin-app-enable-printing"><span>虚拟打印机 (PDF)</span></label>
            </div>
          </section>

          <section class="admin-app-dialog__subsection">
            <h4>本地化</h4>
            <div class="admin-app-dialog__grid">
              <label>
                <span>时区</span>
                <select v-model="form.timezone" data-testid="admin-app-timezone">
                  <option :value="null">自动</option>
                  <option value="Asia/Shanghai">Asia/Shanghai</option>
                  <option value="Asia/Hong_Kong">Asia/Hong_Kong</option>
                  <option value="Asia/Taipei">Asia/Taipei</option>
                  <option value="Asia/Tokyo">Asia/Tokyo</option>
                  <option value="Asia/Seoul">Asia/Seoul</option>
                  <option value="UTC">UTC</option>
                  <option value="America/New_York">America/New_York</option>
                  <option value="Europe/London">Europe/London</option>
                </select>
              </label>
              <label>
                <span>键盘布局</span>
                <select v-model="form.keyboard_layout" data-testid="admin-app-keyboard-layout">
                  <option :value="null">自动</option>
                  <option value="en-us-qwerty">English (US)</option>
                  <option value="ja-jp-qwerty">日本語</option>
                  <option value="de-de-qwertz">Deutsch</option>
                  <option value="fr-fr-azerty">Français</option>
                  <option value="zh-cn-qwerty">中文</option>
                  <option value="ko-kr">한국어</option>
                </select>
              </label>
            </div>
          </section>
        </div>
      </details>

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
import { computed, reactive, ref, watch } from 'vue'

import AdminPoolAttachmentsEditor from '@/modules/admin/components/AdminPoolAttachmentsEditor.vue'
import type {
  AdminAppFormPayload,
  AdminAppRecord,
  AdminPoolRecord,
  AdminScriptProfile,
  AdminWorkerGroup,
  ColorDepth,
  PoolAttachments,
  ScriptExecutorKey,
  TransferPolicy,
} from '@/modules/admin/types/apps'

const props = defineProps<{
  open: boolean
  mode: 'create' | 'edit'
  saving: boolean
  pools: AdminPoolRecord[]
  workerGroups: AdminWorkerGroup[]
  scriptProfiles: AdminScriptProfile[]
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

const scriptPythonEnvText = ref('')
const localError = ref('')

function defaultForm(): AdminAppFormPayload {
  return {
    name: '',
    icon: 'desktop',
    app_kind: 'commercial_software',
    protocol: 'rdp',
    hostname: '',
    port: 3389,
    rdp_username: '',
    rdp_password: '',
    domain: '',
    security: 'nla',
    ignore_cert: true,
    remote_app: '',
    remote_app_dir: '',
    remote_app_args: '',
    color_depth: null,
    disable_gfx: true,
    resize_method: 'display-update',
    enable_wallpaper: false,
    enable_font_smoothing: true,
    disable_copy: false,
    disable_paste: false,
    enable_audio: true,
    enable_audio_input: false,
    enable_printing: false,
    disable_download: null,
    disable_upload: null,
    timezone: null,
    keyboard_layout: null,
    pool_id: null,
    member_max_concurrent: 1,
    is_active: true,
    script_enabled: false,
    script_profile_key: null,
    script_executor_key: null,
    script_worker_group_id: null,
    script_scratch_root: null,
    script_python_executable: null,
    script_python_env: null,
  }
}

const form = reactive<AdminAppFormPayload>(defaultForm())

const selectedScriptProfile = computed(() => {
  return props.scriptProfiles.find((profile) => profile.profile_key === form.script_profile_key) || null
})

const scriptProfileHint = computed(() => {
  const profile = selectedScriptProfile.value
  return profile ? (profile.description || profile.display_name) : '未选择软件预设'
})

const scriptBindingSummary = computed(() => {
  if (!form.script_enabled) return '当前只作为普通 RemoteApp 使用，不会派发到 Worker 节点执行脚本。'
  const group = props.workerGroups.find((item) => item.id === form.script_worker_group_id)
  const profile = selectedScriptProfile.value
  return `脚本将通过 ${form.script_executor_key || '未选择执行器'} 执行，并派发到 Worker 组“${group?.name || '未选择节点组'}”，软件预设为“${profile?.display_name || '未选择软件预设'}”。`
})

function normalizeColorDepth(value: unknown): ColorDepth {
  const depth = Number(value)
  return depth === 8 || depth === 16 || depth === 24 ? depth : null
}

function normalizeTransferPolicy(value: unknown): TransferPolicy {
  if (value === 1 || value === '1' || value === true) return 1
  if (value === 0 || value === '0' || value === false) return 0
  return null
}

function normalizePositiveId(value: unknown): number | null {
  const id = Number(value)
  return Number.isInteger(id) && id > 0 ? id : null
}

function normalizeExecutorKey(value: unknown): ScriptExecutorKey | null {
  return value === 'python_api' || value === 'command_statusfile' ? value : null
}

function trimText(value: unknown) {
  return String(value ?? '').trim()
}

function nullableText(value: unknown) {
  const text = trimText(value)
  return text || null
}

function normalizeJsonEnv(value: unknown) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  const normalized: Record<string, string> = {}
  Object.entries(value).forEach(([key, item]) => {
    normalized[String(key)] = String(item)
  })
  return Object.keys(normalized).length ? normalized : null
}

function envToText(value: Record<string, string> | null | undefined) {
  return value && Object.keys(value).length ? JSON.stringify(value) : ''
}

function hydrateForm(app: AdminAppRecord | null) {
  Object.assign(form, defaultForm(), {
    name: app?.name || '',
    icon: app?.icon || 'desktop',
    app_kind: app?.app_kind || 'commercial_software',
    protocol: app?.protocol || 'rdp',
    hostname: app?.hostname || '',
    port: app?.port || 3389,
    rdp_username: app?.rdp_username || '',
    rdp_password: app?.rdp_password || '',
    domain: app?.domain || '',
    security: app?.security || 'nla',
    ignore_cert: app?.ignore_cert ?? true,
    remote_app: app?.remote_app || '',
    remote_app_dir: app?.remote_app_dir || '',
    remote_app_args: app?.remote_app_args || '',
    color_depth: normalizeColorDepth(app?.color_depth),
    disable_gfx: app?.disable_gfx ?? true,
    resize_method: app?.resize_method || 'display-update',
    enable_wallpaper: app?.enable_wallpaper ?? false,
    enable_font_smoothing: app?.enable_font_smoothing ?? true,
    disable_copy: app?.disable_copy ?? false,
    disable_paste: app?.disable_paste ?? false,
    enable_audio: app?.enable_audio ?? true,
    enable_audio_input: app?.enable_audio_input ?? false,
    enable_printing: app?.enable_printing ?? false,
    disable_download: normalizeTransferPolicy(app?.disable_download),
    disable_upload: normalizeTransferPolicy(app?.disable_upload),
    timezone: app?.timezone || null,
    keyboard_layout: app?.keyboard_layout || null,
    pool_id: app?.pool_id ?? null,
    member_max_concurrent: app?.member_max_concurrent || 1,
    is_active: app?.is_active ?? true,
    script_enabled: app?.script_enabled ?? false,
    script_profile_key: app?.script_profile_key || null,
    script_executor_key: normalizeExecutorKey(app?.script_executor_key),
    script_worker_group_id: app?.script_worker_group_id ?? null,
    script_scratch_root: app?.script_scratch_root || null,
    script_python_executable: app?.script_python_executable || null,
    script_python_env: normalizeJsonEnv(app?.script_python_env),
  })
  scriptPythonEnvText.value = envToText(form.script_python_env)
  localError.value = ''
}

watch(
  () => [props.open, props.initialApp] as const,
  ([open]) => {
    if (!open) return
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
  emit('pool-change', normalizePositiveId(form.pool_id))
}

function applySelectedScriptProfile() {
  const profile = selectedScriptProfile.value
  if (!profile) return
  form.script_executor_key = profile.executor_key
  form.script_python_executable = profile.python_executable || null
  form.script_python_env = normalizeJsonEnv(profile.python_env)
  scriptPythonEnvText.value = envToText(form.script_python_env)
}

function parseScriptPythonEnv() {
  const text = scriptPythonEnvText.value.trim()
  if (!text) return null
  const parsed = JSON.parse(text)
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('额外环境 JSON 必须是对象')
  }
  return normalizeJsonEnv(parsed)
}

function handleSubmit() {
  localError.value = ''
  if (!trimText(form.name) || !trimText(form.hostname)) {
    localError.value = '名称和主机为必填项'
    return
  }
  if (form.script_enabled && (!form.script_executor_key || !form.script_worker_group_id)) {
    localError.value = '启用脚本模式时必须选择执行器和 Worker 组'
    return
  }

  let parsedEnv: Record<string, string> | null = null
  try {
    parsedEnv = parseScriptPythonEnv()
  } catch {
    localError.value = '额外环境 JSON 格式不合法'
    return
  }

  emit('submit', {
    appId: props.initialApp?.id ?? null,
    payload: {
      ...form,
      name: trimText(form.name),
      icon: trimText(form.icon) || 'desktop',
      protocol: trimText(form.protocol) || 'rdp',
      hostname: trimText(form.hostname),
      port: Number(form.port) || 3389,
      rdp_username: trimText(form.rdp_username),
      rdp_password: String(form.rdp_password ?? ''),
      domain: trimText(form.domain),
      security: trimText(form.security) || 'nla',
      remote_app: trimText(form.remote_app),
      remote_app_dir: trimText(form.remote_app_dir),
      remote_app_args: trimText(form.remote_app_args),
      color_depth: normalizeColorDepth(form.color_depth),
      resize_method: form.resize_method === 'reconnect' ? 'reconnect' : 'display-update',
      disable_download: normalizeTransferPolicy(form.disable_download),
      disable_upload: normalizeTransferPolicy(form.disable_upload),
      timezone: nullableText(form.timezone),
      keyboard_layout: nullableText(form.keyboard_layout),
      pool_id: normalizePositiveId(form.pool_id),
      member_max_concurrent: Number(form.member_max_concurrent) || 1,
      script_profile_key: nullableText(form.script_profile_key),
      script_executor_key: normalizeExecutorKey(form.script_executor_key),
      script_worker_group_id: normalizePositiveId(form.script_worker_group_id),
      script_scratch_root: nullableText(form.script_scratch_root),
      script_python_executable: nullableText(form.script_python_executable),
      script_python_env: parsedEnv,
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
  width: min(1120px, calc(100vw - 32px));
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
.admin-app-dialog__header p,
.admin-app-dialog__section h3,
.admin-app-dialog__attachments h3,
.admin-app-dialog__attachments p,
.admin-app-dialog__subsection h4 {
  margin: 0;
}

.admin-app-dialog__header p,
.admin-app-dialog__hint {
  color: #64748b;
}

.admin-app-dialog__section,
.admin-app-dialog__details,
.admin-app-dialog__attachments {
  display: grid;
  gap: 12px;
  padding: 16px;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  background: #f8fafc;
}

.admin-app-dialog__details summary {
  font-weight: 700;
  cursor: pointer;
}

.admin-app-dialog__details-body {
  display: grid;
  gap: 14px;
  padding-top: 12px;
}

.admin-app-dialog__subsection {
  display: grid;
  gap: 10px;
  padding: 12px;
  border-radius: 12px;
  background: #fff;
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

.admin-app-dialog__wide {
  grid-column: 1 / -1;
}

.admin-app-dialog__checkbox {
  align-self: end;
  display: flex !important;
  align-items: center;
  gap: 8px !important;
}

.admin-app-dialog__attachments {
  background: #fff;
}

.admin-app-dialog__warning {
  padding: 10px 12px;
  border-radius: 10px;
  background: #fff7ed;
  color: #9a3412;
}

.admin-app-dialog__preview {
  padding: 10px 12px;
  border-radius: 10px;
  background: #eef2ff;
  color: #3730a3;
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

@media (max-width: 760px) {
  .admin-app-dialog__grid {
    grid-template-columns: 1fr;
  }
}
</style>
