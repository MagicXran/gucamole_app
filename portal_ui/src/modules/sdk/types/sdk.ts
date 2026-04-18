export type SdkPackageKind = 'cloud_platform' | 'simulation_app'

export type SdkPackageListItem = {
  id: number
  package_kind: SdkPackageKind
  name: string
  summary: string
  homepage_url: string
}

export type SdkAsset = {
  id: number
  version_id: number
  asset_kind: string
  display_name: string
  download_url: string
  size_bytes?: number | null
  sort_order: number
}

export type SdkVersion = {
  id: number
  package_id: number
  version: string
  release_notes: string
  released_at?: string | null
  assets: SdkAsset[]
}

export type SdkPackageDetail = SdkPackageListItem & {
  versions: SdkVersion[]
}
