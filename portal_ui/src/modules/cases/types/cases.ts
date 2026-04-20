export type CaseListItem = {
  id: number
  case_uid: string
  title: string
  summary: string
  app_id: number | null
  published_at: string | null
  asset_count: number
}

export type CaseAsset = {
  id: number
  asset_kind: string
  display_name: string
  package_relative_path: string
  size_bytes: number | null
  sort_order: number
}

export type CaseDetail = CaseListItem & {
  assets: CaseAsset[]
}

export type CaseTransferResponse = {
  case_id: number
  case_uid: string
  target_path: string
  asset_count: number
}
