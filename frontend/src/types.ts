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

export interface Item {
  id: number
  owner: string
  created_at: string
  updated_at: string
  fields: Record<string, any>
}

export interface PaginatedItems {
  total: number
  page: number
  page_size: number
  items: Item[]
}
