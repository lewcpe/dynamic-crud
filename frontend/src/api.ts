import type { Field, Item, PaginatedItems } from "./types"

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
  // fields
  listFields: () => request("/fields") as Promise<Field[]>,
  createField: (data: { field_name: string; field_type: string; field_label: string }) =>
    request("/fields", { method: "POST", body: JSON.stringify(data) }) as Promise<Field>,
  updateField: (id: number, data: { field_label?: string; field_type?: string }) =>
    request(`/fields/${id}`, { method: "PUT", body: JSON.stringify(data) }) as Promise<Field>,
  deleteField: (id: number) =>
    request(`/fields/${id}`, { method: "DELETE" }),
  reorderFields: (order: number[]) =>
    request("/fields/reorder", { method: "POST", body: JSON.stringify(order) }),

  // items
  listItems: (params?: { page?: number; page_size?: number; search?: string; sort_by?: string; sort_dir?: string }) => {
    const sp = new URLSearchParams()
    if (params?.page) sp.set("page", String(params.page))
    if (params?.page_size) sp.set("page_size", String(params.page_size))
    if (params?.search) sp.set("search", params.search)
    if (params?.sort_by) sp.set("sort_by", params.sort_by)
    if (params?.sort_dir) sp.set("sort_dir", params.sort_dir)
    const qs = sp.toString()
    return request(`/items${qs ? `?${qs}` : ""}`) as Promise<PaginatedItems>
  },
  getItem: (id: number) => request(`/items/${id}`) as Promise<Item>,
  createItem: (data: { owner: string; data: Record<string, any> }) =>
    request("/items", { method: "POST", body: JSON.stringify(data) }) as Promise<Item>,
  updateItem: (id: number, data: { owner?: string; data?: Record<string, any> }) =>
    request(`/items/${id}`, { method: "PUT", body: JSON.stringify(data) }) as Promise<Item>,
  deleteItem: (id: number) =>
    request(`/items/${id}`, { method: "DELETE" }),
}
