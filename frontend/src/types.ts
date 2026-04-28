export interface Table {
  id: number
  name: string
  label: string
  created_at: string
}

export interface Field {
  id: number
  table_id: number
  field_name: string
  field_type: "int" | "float" | "text" | "date" | "datetime"
  field_label: string
  field_order: number
  created_at: string
}

export interface Relationship {
  id: number
  from_table_id: number
  to_table_id: number
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
  table_id: number
  item_id: number | null
  label: string | null
}

export interface RelMultiRef {
  rel_id: number
  rel_type: string
  direction: "from" | "to"
  table_id: number
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
