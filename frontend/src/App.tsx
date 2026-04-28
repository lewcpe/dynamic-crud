import { useState, useEffect, useCallback } from "react"
import { api } from "./api"
import type { Field, Item } from "./types"
import FieldManager from "./components/FieldManager"
import DataTable from "./components/DataTable"

export default function App() {
  const [fields, setFields] = useState<Field[]>([])
  const [items, setItems] = useState<Item[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState("")
  const [sortBy, setSortBy] = useState("id")
  const [sortDir, setSortDir] = useState("desc")

  const loadFields = useCallback(async () => {
    const f = await api.listFields()
    setFields(f)
  }, [])

  const loadItems = useCallback(async () => {
    const data = await api.listItems({ page, page_size: 20, search, sort_by: sortBy, sort_dir: sortDir })
    setItems(data.items)
    setTotal(data.total)
  }, [page, search, sortBy, sortDir])

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

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <h1 className="text-xl font-bold">Dynamic CRUD</h1>
          <FieldManager fields={fields} onChange={handleDataChange} />
        </div>
      </header>
      <main className="max-w-7xl mx-auto px-4 py-6">
        <DataTable
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
      </main>
    </div>
  )
}
