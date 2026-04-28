import { useState, useEffect, useCallback } from "react"
import { api } from "./api"
import type { Table, Field, Item } from "./types"
import TableSelector from "./components/TableSelector"
import TableManager from "./components/TableManager"
import FieldManager from "./components/FieldManager"
import DataTable from "./components/DataTable"

export default function App() {
  const [tables, setTables] = useState<Table[]>([])
  const [currentTableId, setCurrentTableId] = useState<number | null>(null)
  const [fields, setFields] = useState<Field[]>([])
  const [items, setItems] = useState<Item[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState("")
  const [sortBy, setSortBy] = useState("id")
  const [sortDir, setSortDir] = useState("desc")

  const loadTables = useCallback(async () => {
    const t = await api.listTables()
    setTables(t)
    if (currentTableId == null && t.length > 0) {
      setCurrentTableId(t[0].id)
    }
  }, [currentTableId])

  useEffect(() => { loadTables() }, [loadTables])

  const loadFields = useCallback(async () => {
    if (currentTableId == null) return
    const f = await api.listFields(currentTableId)
    setFields(f)
  }, [currentTableId])

  const loadItems = useCallback(async () => {
    if (currentTableId == null) return
    const data = await api.listItems(currentTableId, {
      page, page_size: 20, search, sort_by: sortBy, sort_dir: sortDir,
    })
    setItems(data.items)
    setTotal(data.total)
  }, [currentTableId, page, search, sortBy, sortDir])

  useEffect(() => { loadFields() }, [loadFields])
  useEffect(() => { loadItems() }, [loadItems])

  const handleDataChange = () => {
    loadItems()
    loadFields()
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
            <TableManager tables={tables} onChange={handleTablesChanged} />
            {currentTableId != null && (
              <FieldManager tableId={currentTableId} fields={fields} onChange={handleDataChange} />
            )}
          </div>
        </div>
      </header>
      <main className="max-w-7xl mx-auto px-4 py-6">
        {currentTableId == null ? (
          <p className="text-muted-foreground text-center py-12">
            No tables yet. Create one to get started.
          </p>
        ) : (
          <DataTable
            tableId={currentTableId}
            fields={fields}
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
