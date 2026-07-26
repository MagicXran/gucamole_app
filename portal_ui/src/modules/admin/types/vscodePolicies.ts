export type VscodePermissionMap = Record<string, boolean>

export type VscodeControlCatalogItem = {
  code: string
  category: string
  label: string
  enforcement: string
  risk: string
  requires_allowlists: string[]
}

export type LockedSecurityBaselineItem = {
  code: string
  label: string
}

export type VscodeControlCatalog = {
  policy_version: number
  controls: VscodeControlCatalogItem[]
  default_permissions: VscodePermissionMap
  locked_baseline: LockedSecurityBaselineItem[]
}

export type VscodeControlProfilePayload = {
  profile_key: string
  display_name: string
  description: string
  policy_version: number
  is_active: boolean
  permissions: VscodePermissionMap
  allowed_shells: string[]
  allowed_tools: string[]
  allowed_debuggers: string[]
  allowed_extensions: string[]
  allowed_network_targets: string[]
  user_data_root: string
  extensions_root: string
  default_workspace_template: string
}

export type VscodeControlProfile = VscodeControlProfilePayload & {
  id: number
  revision: number
  valid: boolean
  validation_errors: string[]
  created_at?: string | null
  updated_at?: string | null
  guacamole?: Record<string, boolean>
  vscode?: Record<string, unknown>
  applocker?: Record<string, unknown>
  firewall?: Record<string, unknown>
}

export type VscodeControlProfilesResponse = {
  items: VscodeControlProfile[]
}
