<template>
  <div v-if="open" class="admin-app-dialog">
    <div class="admin-app-dialog__panel">
      <header class="admin-app-dialog__header">
        <div>
          <h2>{{ mode === 'edit' ? '编辑运行实例' : '新建运行实例' }}</h2>
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
          <label>
            <span>访问安全模式</span>
            <select v-model="form.security_mode" data-testid="admin-app-security-mode">
              <option value="restricted_remoteapp">一般限制 RemoteApp</option>
              <option value="restricted_vscode">受限 VSCode</option>
              <option value="admin_desktop">管理员桌面</option>
            </select>
          </label>
          <label v-if="form.security_mode === 'restricted_vscode'">
            <span>VSCode 控制策略</span>
            <select v-model="form.vscode_control_profile_id" data-testid="admin-app-vscode-profile">
              <option :value="null">未选择</option>
              <option
                v-for="profile in vscodeControlProfiles"
                :key="profile.id"
                :value="profile.id"
                :disabled="!(profile.is_active && profile.valid)"
              >
                {{ profile.display_name }}（{{ profile.is_active && profile.valid ? '可绑定' : '未就绪' }}）
              </option>
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
            <span>容量池</span>
            <select v-model="form.pool_id" data-testid="admin-app-pool">
              <option :value="null">独立运行（不加入容量池）</option>
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
          <label><span>工作目录</span><input v-model="form.remote_app_dir" placeholder="留空则自动使用当前用户的资料空间" data-testid="admin-app-remote-dir"></label>
          <label class="admin-app-dialog__wide"><span>命令参数</span><input v-model="form.remote_app_args" data-testid="admin-app-remote-args"></label>
        </div>
        <p class="admin-app-dialog__hint">
          工作目录留空时，启动阶段按当前 Portal 用户展开为 <code>\\tsclient\用户名称 的资料空间</code>；显式填写时保留应用专用目录。一般限制会强制关闭剪贴板、浏览器传输、打印和麦克风。
        </p>
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

import type {
  AdminAppFormPayload,
  AdminAppRecord,
  AdminPoolRecord,
  AdminScriptProfile,
  AdminWorkerGroup,
  ColorDepth,
  ScriptExecutorKey,
  TransferPolicy,
} from '@/modules/admin/types/apps'
import type { VscodeControlProfile } from '@/modules/admin/types/vscodePolicies'

const props = withDefaults(defineProps<{
  open: boolean
  mode: 'create' | 'edit'
  saving: boolean
  pools: AdminPoolRecord[]
  workerGroups: AdminWorkerGroup[]
  scriptProfiles: AdminScriptProfile[]
  vscodeControlProfiles?: VscodeControlProfile[]
  initialApp: AdminAppRecord | null
}>(), {
  vscodeControlProfiles: () => [],
})

const emit = defineEmits<{
  close: []
  submit: [{ appId: number | null; payload: AdminAppFormPayload }]
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
    security_mode: 'restricted_remoteapp',
    vscode_control_profile_id: null,
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
    security_mode: app?.security_mode || 'restricted_remoteapp',
    vscode_control_profile_id: app?.vscode_control_profile_id ?? null,
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

watch(
  () => form.security_mode,
  (mode) => {
    if (mode !== 'restricted_vscode') form.vscode_control_profile_id = null
  },
)

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
  if (form.security_mode !== 'admin_desktop' && !trimText(form.remote_app)) {
    localError.value = '一般限制 RemoteApp 和受限 VSCode 必须填写 RemoteApp'
    return
  }
  if (form.security_mode === 'restricted_vscode' && !normalizePositiveId(form.vscode_control_profile_id)) {
    localError.value = '受限 VSCode 必须选择已就绪的控制策略'
    return
  }
  if (form.security_mode === 'restricted_vscode') {
    const selectedProfile = props.vscodeControlProfiles.find((profile) => profile.id === normalizePositiveId(form.vscode_control_profile_id))
    if (!selectedProfile?.is_active || !selectedProfile.valid) {
      localError.value = '受限 VSCode 只能绑定已启用且有效的控制策略'
      return
    }
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
      vscode_control_profile_id: normalizePositiveId(form.vscode_control_profile_id),
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
  })
}
</script>

<style scoped>
.admin-app-dialog {
  position: fixed;
  inset: 0;
  display: grid;
  place-items: center;
  background: rgba(10, 11, 13, 0.52);
  backdrop-filter: blur(8px);
  z-index: 20;
}

.admin-app-dialog__panel {
  width: min(1120px, calc(100vw - 32px));
  max-height: calc(100vh - 32px);
  overflow: auto;
  display: grid;
  gap: 18px;
  padding: 24px;
  border: 1px solid var(--portal-color-border);
  border-radius: 24px;
  background: var(--portal-color-surface);
  box-shadow: 0 28px 90px rgba(10, 11, 13, 0.24);
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
.admin-app-dialog__subsection h4 {
  margin: 0;
}

.admin-app-dialog__header p,
.admin-app-dialog__hint {
  color: var(--portal-color-body);
}

.admin-app-dialog__section,
.admin-app-dialog__details {
  display: grid;
  gap: 12px;
  padding: 16px;
  border: 1px solid var(--portal-color-border);
  border-radius: 18px;
  background: var(--portal-color-page);
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
  border-radius: 16px;
  background: var(--portal-color-surface);
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

.admin-app-dialog__warning {
  padding: 10px 12px;
  border-radius: 14px;
  background: #fff7ed;
  color: var(--portal-color-warning);
}

.admin-app-dialog__preview {
  padding: 10px 12px;
  border-radius: 14px;
  background: rgba(0, 82, 255, 0.08);
  color: var(--portal-color-primary);
}

input,
select,
button {
  border-radius: 14px;
}

input,
select {
  border: 1px solid transparent;
  padding: 10px 12px;
  background: var(--portal-color-surface-soft);
  color: var(--portal-color-ink);
}

input:focus,
select:focus {
  outline: none;
  border-color: rgba(0, 82, 255, 0.2);
  background: var(--portal-color-surface);
}

button {
  min-height: 42px;
  border: 1px solid var(--portal-color-border);
  background: var(--portal-color-surface);
  color: var(--portal-color-ink);
  padding: 0 16px;
  cursor: pointer;
  transition: border-color 0.2s ease, color 0.2s ease;
}

button:hover:not(:disabled) {
  border-color: var(--portal-color-primary);
  color: var(--portal-color-primary);
}

@media (max-width: 760px) {
  .admin-app-dialog__grid {
    grid-template-columns: 1fr;
  }
}
</style>
