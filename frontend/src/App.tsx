import { useState, useEffect, useCallback } from "react"
import { api } from "./api"
import type { Table, Field, Relationship, Item, User } from "./types"
import TableSelector from "./components/TableSelector"
import TableManager from "./components/TableManager"
import FieldManager from "./components/FieldManager"
import RelationshipManager from "./components/RelationshipManager"
import DataTable from "./components/DataTable"

export default function App() {
  const [user, setUser] = useState<User | null>(null)
  const [tables, setTables] = useState<Table[]>([])
  const [currentTableId, setCurrentTableId] = useState<number | null>(null)
  const [fields, setFields] = useState<Field[]>([])
  const [relationships, setRelationships] = useState<Relationship[]>([])
  const [items, setItems] = useState<Item[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState("")
  const [sortBy, setSortBy] = useState("id")
  const [sortDir, setSortDir] = useState("desc")
  const [authMode, setAuthMode] = useState<"login" | "register">("login")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [name, setName] = useState("")
  const [authError, setAuthError] = useState("")

  useEffect(() => {
    const token = localStorage.getItem("token")
    if (token) {
      api.getMe().then(setUser).catch(() => localStorage.removeItem("token"))
    }
  }, [])

  const handleAuth = async () => {
    setAuthError("")
    try {
      const resp = authMode === "login"
        ? await api.login({ email, password })
        : await api.register({ email, password, name })
      localStorage.setItem("token", resp.access_token)
      setUser(resp.user)
      setEmail("")
      setPassword("")
      setName("")
    } catch (e: any) {
      setAuthError(e.message)
    }
  }

  const handleLogout = () => {
    localStorage.removeItem("token")
    setUser(null)
    setTables([])
    setCurrentTableId(null)
  }

  const loadTables = useCallback(async () => {
    const t = await api.listTables()
    setTables(t)
    if (currentTableId == null && t.length > 0) {
      setCurrentTableId(t[0].id)
    }
  }, [currentTableId])

  useEffect(() => { if (user) loadTables() }, [user, loadTables])

  const loadFields = useCallback(async () => {
    if (currentTableId == null) return
    const f = await api.listFields(currentTableId)
    setFields(f)
  }, [currentTableId])

  const loadRelationships = useCallback(async () => {
    if (currentTableId == null) return
    const r = await api.listRelationships(currentTableId)
    setRelationships(r)
  }, [currentTableId])

  const loadItems = useCallback(async () => {
    if (currentTableId == null) return
    const data = await api.listItems(currentTableId, {
      page, page_size: 20, search, sort_by: sortBy, sort_dir: sortDir,
    })
    setItems(data.items)
    setTotal(data.total)
  }, [currentTableId, page, search, sortBy, sortDir])

  useEffect(() => { if (user) loadFields() }, [user, loadFields])
  useEffect(() => { if (user) loadRelationships() }, [user, loadRelationships])
  useEffect(() => { if (user) loadItems() }, [user, loadItems])

  const handleDataChange = () => {
    loadItems()
    loadFields()
    loadRelationships()
  }

  const handleSearch = (s: string) => {
    setSearch(s)
    setPage(1)
  }

  const handleSort = (field: string) => {
    if (sortBy === field) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"))
    } else {
      setSortBy(field)
      setSortDir("asc")
    }
    setPage(1)
  }

  const handleTableChange = (id: number) => {
    setCurrentTableId(id)
    setPage(1)
    setSearch("")
    setSortBy("id")
    setSortDir("desc")
  }

  const handleTablesChanged = () => {
    loadTables().then(() => {
      if (tables.length > 0 && !tables.find((t) => t.id === currentTableId)) {
        setCurrentTableId(null)
      }
    })
  }

  if (!user) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="w-full max-w-sm space-y-4 p-6">
          <h1 className="text-2xl font-bold text-center">Dynamic CRUD</h1>
          <div className="space-y-2">
            <div className="flex gap-2">
              <button
                className={`flex-1 py-2 text-sm ${authMode === "login" ? "border-b-2 border-primary font-bold" : "text-muted-foreground"}`}
                onClick={() => setAuthMode("login")}
              >
                Login
              </button>
              <button
                className={`flex-1 py-2 text-sm ${authMode === "register" ? "border-b-2 border-primary font-bold" : "text-muted-foreground"}`}
                onClick={() => setAuthMode("register")}
              >
                Register
              </button>
            </div>
            {authMode === "register" && (
              <input
                className="w-full border rounded px-3 py-2 text-sm"
                placeholder="Name"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            )}
            <input
              className="w-full border rounded px-3 py-2 text-sm"
              placeholder="Email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <input
              className="w-full border rounded px-3 py-2 text-sm"
              placeholder="Password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            {authError && <p className="text-sm text-destructive">{authError}</p>}
            <button
              className="w-full bg-primary text-primary-foreground py-2 rounded text-sm font-medium"
              onClick={handleAuth}
            >
              {authMode === "login" ? "Login" : "Register"}
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between gap-4">
          <h1 className="text-xl font-bold shrink-0">Dynamic CRUD</h1>
          <div className="flex items-center gap-3">
            <TableSelector
              tables={tables}
              currentTableId={currentTableId}
              onTableChange={handleTableChange}
            />
            {user.role === "admin" && (
              <>
                <TableManager tables={tables} onChange={handleTablesChanged} />
                {currentTableId != null && (
                  <>
                    <FieldManager tableId={currentTableId} fields={fields} onChange={handleDataChange} />
                    <RelationshipManager
                      tableId={currentTableId}
                      tables={tables}
                      relationships={relationships}
                      onChange={handleDataChange}
                    />
                  </>
                )}
              </>
            )}
          </div>
          <div className="flex items-center gap-2 text-sm">
            <span className="text-muted-foreground">{user.name} ({user.role})</span>
            <button
              className="text-muted-foreground hover:text-foreground"
              onClick={handleLogout}
            >
              Logout
            </button>
          </div>
        </div>
      </header>
      <main className="max-w-7xl mx-auto px-4 py-6">
        {currentTableId == null ? (
          <p className="text-muted-foreground text-center py-12">
            {tables.length === 0 ? "No tables yet. Create one to get started." : "Select a table."}
          </p>
        ) : (
          <DataTable
            tableId={currentTableId}
            fields={fields}
            relationships={relationships}
            tables={tables}
            items={items}
            total={total}
            page={page}
            pageSize={20}
            search={search}
            sortBy={sortBy}
            sortDir={sortDir}
            onDataChange={handleDataChange}
            onSearchChange={handleSearch}
            onPageChange={setPage}
            onSortChange={handleSort}
          />
        )}
      </main>
    </div>
  )
}
