<template>
  <section class="admin-ops-view">
    <header class="admin-ops-view__header">
      <div>
        <h1>VSCode 受控开发策略</h1>
        <p>集中管理权限目录、程序/扩展/网络白名单和最终 Guacamole 通道参数。</p>
      </div>
      <button type="button" data-testid="vscode-policy-create" @click="openCreate">新建策略</button>
    </header>

    <div v-if="store.errorMessage" class="admin-ops-view__state admin-ops-view__state--error">{{ store.errorMessage }}</div>
    <div v-else-if="store.loading" class="admin-ops-view__state">策略加载中...</div>
    <table v-else class="admin-ops-view__table">
      <thead>
        <tr>
          <th>标识</th>
          <th>名称</th>
          <th>版本</th>
          <th>修订</th>
          <th>有效性</th>
          <th>状态</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="store.profiles.length === 0"><td colspan="7">暂无 VSCode 策略</td></tr>
        <tr v-for="profile in store.profiles" :key="profile.id">
          <td>{{ profile.profile_key }}</td>
          <td>{{ profile.display_name }}</td>
          <td>v{{ profile.policy_version }}</td>
          <td>r{{ profile.revision }}</td>
          <td :class="profile.valid ? 'policy-valid' : 'policy-invalid'">
            {{ profile.valid ? '有效' : profile.validation_errors.join('；') }}
          </td>
          <td>{{ profile.is_active ? '启用' : '停用' }}</td>
          <td class="policy-actions">
            <button type="button" :data-testid="`vscode-policy-edit-${profile.id}`" @click="openEdit(profile)">编辑</button>
            <button type="button" @click="remove(profile.id)">删除</button>
          </td>
        </tr>
      </tbody>
    </table>

    <VscodePolicyFormDialog
      :open="dialogOpen"
      :saving="store.saving"
      :catalog="store.catalog"
      :initial-profile="selectedProfile"
      @close="closeDialog"
      @submit="save"
    />
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import VscodePolicyFormDialog from '@/modules/admin/components/VscodePolicyFormDialog.vue'
import { useAdminVscodePoliciesStore } from '@/modules/admin/stores/vscodePolicies'
import type { VscodeControlProfile, VscodeControlProfilePayload } from '@/modules/admin/types/vscodePolicies'
import '@/modules/admin/views/admin-ops.css'

const store = useAdminVscodePoliciesStore()
const dialogOpen = ref(false)
const selectedProfile = ref<VscodeControlProfile | null>(null)

function openCreate() {
  selectedProfile.value = null
  dialogOpen.value = true
}

function openEdit(profile: VscodeControlProfile) {
  selectedProfile.value = profile
  dialogOpen.value = true
}

function closeDialog() {
  selectedProfile.value = null
  dialogOpen.value = false
}

async function save({ profileId, payload }: { profileId: number | null; payload: VscodeControlProfilePayload }) {
  await store.saveProfile(profileId, payload)
  closeDialog()
}

async function remove(profileId: number) {
  if (typeof window.confirm === 'function' && !window.confirm('确定删除这个 VSCode 策略？')) return
  await store.removeProfile(profileId)
}

onMounted(() => store.bootstrap())
</script>

<style scoped>
.policy-actions {
  display: flex;
  gap: 8px;
}

.policy-valid {
  color: var(--portal-color-success);
}

.policy-invalid {
  max-width: 420px;
  color: var(--portal-color-warning);
}
</style>
