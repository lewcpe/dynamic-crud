import type { Table, Field, Item, PaginatedItems } from "./types"

const BASE = "/api"

async function request(path: string, options?: RequestInit) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || "Request failed")
  }
  return res.json()
}

export const api = {
  // tables
  listTables: () => request("/tables") as Promise<Table[]>,
  createTable: (data: { name: string; label?: string }) =>
    request("/tables", { method: "POST", body: JSON.stringify(data) }) as Promise<Table>,
  updateTable: (id: number, data: { name?: string; label?: string }) =>
    request(`/tables/${id}`, { method: "PUT", body: JSON.stringify(data) }) as Promise<Table>,
  deleteTable: (id: number) => request(`/tables/${id}`, { method: "DELETE" }),

  // fields (table-scoped)
  listFields: (tableId: number) =>
    request(`/tables/${tableId}/fields`) as Promise<Field[]>,
  createField: (tableId: number, data: { field_name: string; field_type: string; field_label: string }) =>
    request(`/tables/${tableId}/fields`, { method: "POST", body: JSON.stringify(data) }) as Promise<Field>,
  updateField: (tableId: number, id: number, data: { field_label?: string; field_type?: string }) =>
    request(`/tables/${tableId}/fields/${id}`, { method: "PUT", body: JSON.stringify(data) }) as Promise<Field>,
  deleteField: (tableId: number, id: number) =>
    request(`/tables/${tableId}/fields/${id}`, { method: "DELETE" }),
  reorderFields: (tableId: number, order: number[]) =>
    request(`/tables/${tableId}/fields/reorder`, { method: "POST", body: JSON.stringify(order) }),

  // items (table-scoped)
  listItems: (tableId: number, params?: { page?: number; page_size?: number; search?: string; sort_by?: string; sort_dir?: string }) => {
    const sp = new URLSearchParams()
    if (params?.page) sp.set("page", String(params.page))
    if (params?.page_size) sp.set("page_size", String(params.page_size))
    if (params?.search) sp.set("search", params.search)
    if (params?.sort_by) sp.set("sort_by", params.sort_by)
    if (params?.sort_dir) sp.set("sort_dir", params.sort_dir)
    const qs = sp.toString()
    return request(`/tables/${tableId}/items${qs ? `?${qs}` : ""}`) as Promise<PaginatedItems>
  },
  getItem: (tableId: number, id: number) =>
    request(`/tables/${tableId}/items/${id}`) as Promise<Item>,
  createItem: (tableId: number, data: { owner: string; data: Record<string, any> }) =>
    request(`/tables/${tableId}/items`, { method: "POST", body: JSON.stringify(data) }) as Promise<Item>,
  updateItem: (tableId: number, id: number, data: { owner?: string; data?: Record<string, any> }) =>
    request(`/tables/${tableId}/items/${id}`, { method: "PUT", body: JSON.stringify(data) }) as Promise<Item>,
  deleteItem: (tableId: number, id: number) =>
    request(`/tables/${tableId}/items/${id}`, { method: "DELETE" }),
}
