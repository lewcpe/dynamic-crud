export interface Table {
  id: number
  name: string
  label: string
  represent: string
  created_at: string
}

export interface Field {
  id: number
  table_id: number
  field_name: string
  field_type: "int" | "float" | "text" | "date" | "datetime" | "file" | "files"
  field_label: string
  field_order: number
  created_at: string
}

export interface Relationship {
  id: number
  from_table_id: number
  to_table_id: number | null
  to_system_table: string | null
  rel_name: string
  rel_label: string
  rel_type: "1-1" | "1-n" | "n-n"
  from_label: string
  to_label: string
  created_at: string
}

export interface RelSingleRef {
  rel_id: number
  rel_type: string
  direction: "from" | "to"
  table_id: number | null
  system_table?: string | null
  item_id: number | null
  label: string | null
}

export interface RelMultiRef {
  rel_id: number
  rel_type: string
  direction: "from" | "to"
  table_id: number | null
  system_table?: string | null
  items: { item_id: number; label: string }[]
}

export type RelValue = RelSingleRef | RelMultiRef

export interface Item {
  id: number
  owner: string
  created_at: string
  updated_at: string
  fields: Record<string, any>
  relationships?: Record<string, RelValue>
}

export interface PaginatedItems {
  total: number
  page: number
  page_size: number
  items: Item[]
}

export interface User {
  id: number
  email: string
  name: string
  role: "admin" | "user"
  manager_id: number | null
  created_at: string
  groups?: Group[]
}

export interface Group {
  id: number
  name: string
  description: string
  created_at: string
}

export interface Permission {
  id: number
  table_id: number
  target_type: "user" | "group" | "role"
  target_id: number | null
  target_role: string | null
  list_rule: string | null
  view_rule: string | null
  create_rule: string | null
  update_rule: string | null
  delete_rule: string | null
  created_at: string
}

export interface FileAttachment {
  id: number
  table_id: number
  item_id: number
  field_name: string
  filename: string
  mime_type: string
  size: number
  uploader_id: number | null
  created_at: string
}

export interface Comment {
  id: number
  table_id: number
  item_id: number
  user_id: number
  content: string
  user_name: string
  user_email: string
  created_at: string
  updated_at: string
}

export interface SystemItem {
  id: number
  label: string
}
