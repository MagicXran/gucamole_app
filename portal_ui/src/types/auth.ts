export type SessionUser = {
  user_id: number
  username: string
  display_name: string
  is_admin: boolean
}

export type SessionMenuNode = {
  key: string
  title: string
  path?: string
  children?: SessionMenuNode[]
}

export type SessionBootstrapPayload = {
  authenticated: boolean
  auth_source: string
  user: SessionUser | null
  capabilities: string[]
  menu_tree: SessionMenuNode[]
  org_context: Record<string, unknown>
}
