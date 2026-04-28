import type {
  Table, Field, Relationship, Item, PaginatedItems,
  User, Group, Permission, FileAttachment, Comment,
} from "./types"

const BASE = "/api"

function getToken(): string | null {
  return localStorage.getItem("token")
}

async function request(path: string, options?: RequestInit) {
  const token = getToken()
  const headers: Record<string, string> = { "Content-Type": "application/json" }
  if (token) headers["Authorization"] = `Bearer ${token}`

  const res = await fetch(`${BASE}${path}`, { headers, ...options })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || "Request failed")
  }
  return res.json()
}

async function upload(path: string, formData: FormData) {
  const token = getToken()
  const headers: Record<string, string> = {}
  if (token) headers["Authorization"] = `Bearer ${token}`

  const res = await fetch(`${BASE}${path}`, { method: "POST", headers, body: formData })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || "Request failed")
  }
  return res.json()
}

export const api = {
  // auth
  register: (data: { email: string; password: string; name?: string }) =>
    request("/auth/register", { method: "POST", body: JSON.stringify(data) }) as Promise<{ access_token: string; user: User }>,
  login: (data: { email: string; password: string }) =>
    request("/auth/login", { method: "POST", body: JSON.stringify(data) }) as Promise<{ access_token: string; user: User }>,
  getMe: () => request("/auth/me") as Promise<User>,

  // users (admin)
  listUsers: () => request("/users") as Promise<User[]>,
  updateUser: (id: number, data: { name?: string; role?: string }) =>
    request(`/users/${id}`, { method: "PUT", body: JSON.stringify(data) }) as Promise<User>,
  deleteUser: (id: number) => request(`/users/${id}`, { method: "DELETE" }),
  makeAdmin: (id: number) => request(`/users/${id}/make-admin`, { method: "POST" }),
  removeAdmin: (id: number) => request(`/users/${id}/remove-admin`, { method: "POST" }),
  setManager: (id: number, managerId: number | null) =>
    request(`/users/${id}/manager`, { method: "PUT", body: JSON.stringify({ manager_id: managerId }) }) as Promise<User>,

  // groups (admin)
  listGroups: () => request("/groups") as Promise<Group[]>,
  createGroup: (data: { name: string; description?: string }) =>
    request("/groups", { method: "POST", body: JSON.stringify(data) }) as Promise<Group>,
  updateGroup: (id: number, data: { name?: string; description?: string }) =>
    request(`/groups/${id}`, { method: "PUT", body: JSON.stringify(data) }) as Promise<Group>,
  deleteGroup: (id: number) => request(`/groups/${id}`, { method: "DELETE" }),
  listGroupMembers: (id: number) => request(`/groups/${id}/members`) as Promise<User[]>,
  addGroupMember: (id: number, userId: number) =>
    request(`/groups/${id}/members`, { method: "POST", body: JSON.stringify({ user_id: userId }) }),
  removeGroupMember: (id: number, userId: number) =>
    request(`/groups/${id}/members/${userId}`, { method: "DELETE" }),

  // tables
  listTables: () => request("/tables") as Promise<Table[]>,
  createTable: (data: { name: string; label?: string; represent?: string }) =>
    request("/tables", { method: "POST", body: JSON.stringify(data) }) as Promise<Table>,
  updateTable: (id: number, data: { name?: string; label?: string; represent?: string }) =>
    request(`/tables/${id}`, { method: "PUT", body: JSON.stringify(data) }) as Promise<Table>,
  deleteTable: (id: number) => request(`/tables/${id}`, { method: "DELETE" }),

  // system tables (for relationship dropdowns)
  listSystemUsers: () => request("/system/users") as Promise<{ id: number; label: string }[]>,
  listSystemGroups: () => request("/system/groups") as Promise<{ id: number; label: string }[]>,

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

  // relationships (table-scoped)
  listRelationships: (tableId: number) =>
    request(`/tables/${tableId}/relationships`) as Promise<Relationship[]>,
  createRelationship: (tableId: number, data: {
    to_table_id: number; rel_name: string; rel_label?: string;
    rel_type: string; from_label?: string; to_label?: string;
  }) =>
    request(`/tables/${tableId}/relationships`, { method: "POST", body: JSON.stringify(data) }) as Promise<Relationship>,
  updateRelationship: (tableId: number, id: number, data: { rel_label?: string; from_label?: string; to_label?: string }) =>
    request(`/tables/${tableId}/relationships/${id}`, { method: "PUT", body: JSON.stringify(data) }) as Promise<Relationship>,
  deleteRelationship: (tableId: number, id: number) =>
    request(`/tables/${tableId}/relationships/${id}`, { method: "DELETE" }),
  setRelationshipLinks: (tableId: number, relId: number, data: { item_id: number; target_ids: number[] }) =>
    request(`/tables/${tableId}/relationships/${relId}/link`, { method: "POST", body: JSON.stringify(data) }),

  // permissions (table-scoped, admin)
  listPermissions: (tableId: number) =>
    request(`/tables/${tableId}/permissions`) as Promise<Permission[]>,
  createPermission: (tableId: number, data: {
    target_type: string; target_id?: number; target_role?: string;
    list_rule?: string | null; view_rule?: string | null;
    create_rule?: string | null; update_rule?: string | null; delete_rule?: string | null;
  }) =>
    request(`/tables/${tableId}/permissions`, { method: "POST", body: JSON.stringify(data) }) as Promise<Permission>,
  updatePermission: (tableId: number, id: number, data: {
    list_rule?: string | null; view_rule?: string | null;
    create_rule?: string | null; update_rule?: string | null; delete_rule?: string | null;
  }) =>
    request(`/tables/${tableId}/permissions/${id}`, { method: "PUT", body: JSON.stringify(data) }) as Promise<Permission>,
  deletePermission: (tableId: number, id: number) =>
    request(`/tables/${tableId}/permissions/${id}`, { method: "DELETE" }),
  getMyPermissions: (tableId: number) =>
    request(`/tables/${tableId}/my-permissions`) as Promise<Record<string, boolean>>,

  // items (table-scoped)
  listItemOptions: (tableId: number) =>
    request(`/tables/${tableId}/items/options`) as Promise<{ id: number; label: string }[]>,
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

  // files
  uploadFile: (tableId: number, itemId: number, file: File, fieldName?: string) => {
    const fd = new FormData()
    fd.append("file", file)
    if (fieldName) fd.append("field_name", fieldName)
    return upload(`/tables/${tableId}/items/${itemId}/files`, fd) as Promise<FileAttachment>
  },
  listFiles: (tableId: number, itemId: number) =>
    request(`/tables/${tableId}/items/${itemId}/files`) as Promise<FileAttachment[]>,
  downloadFile: (fileId: number) => {
    const token = getToken()
    return fetch(`${BASE}/files/${fileId}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
  },
  deleteFile: (fileId: number) => request(`/files/${fileId}`, { method: "DELETE" }),

  // comments
  listComments: (tableId: number, itemId: number) =>
    request(`/tables/${tableId}/items/${itemId}/comments`) as Promise<Comment[]>,
  createComment: (tableId: number, itemId: number, content: string) =>
    request(`/tables/${tableId}/items/${itemId}/comments`, { method: "POST", body: JSON.stringify({ content }) }) as Promise<Comment>,
  updateComment: (commentId: number, content: string) =>
    request(`/comments/${commentId}`, { method: "PUT", body: JSON.stringify({ content }) }) as Promise<Comment>,
  deleteComment: (commentId: number) => request(`/comments/${commentId}`, { method: "DELETE" }),
}
