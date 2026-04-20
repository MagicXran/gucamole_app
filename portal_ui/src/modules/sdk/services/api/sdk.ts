import http from '@/services/http'

import type { SdkPackageDetail, SdkPackageKind, SdkPackageListItem } from '@/modules/sdk/types/sdk'

export function getSdkPackages(packageKind: SdkPackageKind) {
  return http.get<SdkPackageListItem[]>('/api/sdks', {
    params: {
      package_kind: packageKind,
    },
  })
}

export function getSdkPackageDetail(packageId: number) {
  return http.get<SdkPackageDetail>(`/api/sdks/${packageId}`)
}

export function createSdkAssetDownloadToken(assetId: number) {
  return http.post<{ token: string; expires_in: number }>(`/api/sdks/assets/${assetId}/download-token`)
}

export function getSdkAssetDownloadUrl(assetId: number, token: string) {
  return `/api/sdks/assets/${assetId}/download?_token=${encodeURIComponent(token)}`
}
