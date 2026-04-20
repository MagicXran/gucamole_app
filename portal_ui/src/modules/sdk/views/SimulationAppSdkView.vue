<template>
  <section class="sdk-center-view">
    <header class="sdk-center-view__header">
      <div>
        <h1>仿真AppSDK</h1>
        <p>面向仿真 App 开发的 SDK 包、版本与下载资产。</p>
      </div>
      <button type="button" @click="reload">刷新</button>
    </header>

    <div class="sdk-center-view__content">
      <SdkPackageList
        v-model:keyword="sdkStore.keyword"
        :error-message="sdkStore.errorMessage"
        :loading="sdkStore.loading"
        :packages="sdkStore.filteredPackages"
        :selected-package-id="sdkStore.selectedPackageId"
        @select="sdkStore.selectPackage"
      />
      <SdkVersionPanel
        :detail="sdkStore.selectedDetail"
        :error-message="sdkStore.detailErrorMessage"
        :loading="sdkStore.detailLoading"
        @download="downloadAsset"
      />
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'

import SdkPackageList from '@/modules/sdk/components/SdkPackageList.vue'
import SdkVersionPanel from '@/modules/sdk/components/SdkVersionPanel.vue'
import { createSdkAssetDownloadToken, getSdkAssetDownloadUrl } from '@/modules/sdk/services/api/sdk'
import { useSdkStore } from '@/modules/sdk/stores/sdk'

const sdkStore = useSdkStore()

async function reload() {
  await sdkStore.loadPackages('simulation_app')
}

async function downloadAsset(assetId: number) {
  const downloadWindow = window.open('', '_blank')
  if (downloadWindow) {
    downloadWindow.opener = null
  }
  const response = await createSdkAssetDownloadToken(assetId)
  const downloadUrl = getSdkAssetDownloadUrl(assetId, response.data.token)
  if (downloadWindow) {
    downloadWindow.location.href = downloadUrl
    return
  }
  window.location.href = downloadUrl
}

onMounted(async () => {
  await reload()
})
</script>

<style scoped>
.sdk-center-view {
  display: grid;
  gap: 18px;
  padding: 24px;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
}

.sdk-center-view__header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

.sdk-center-view__header h1,
.sdk-center-view__header p {
  margin: 0;
}

.sdk-center-view__content {
  display: grid;
  grid-template-columns: minmax(240px, 320px) 1fr;
  gap: 20px;
}

button {
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  background: #fff;
  color: #1e3a8a;
  padding: 8px 12px;
  cursor: pointer;
}
</style>
