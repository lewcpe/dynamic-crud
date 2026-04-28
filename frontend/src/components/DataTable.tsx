import { useState, useEffect } from "react"
import type { Field, Item, Relationship, Table, RelValue } from "../types"
import { api } from "../api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Table as UiTable,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Pencil, Trash2, ArrowUpDown, Link2, Columns3 } from "lucide-react"
import ItemForm from "./ItemForm"

interface Props {
  tableId: number
  fields: Field[]
  relationships: Relationship[]
  tables: Table[]
  items: Item[]
  total: number
  page: number
  pageSize: number
  search: string
  sortBy: string
  sortDir: string
  onDataChange: () => void
  onSearchChange: (s: string) => void
  onPageChange: (p: number) => void
  onSortChange: (field: string) => void
}

export default function DataTable({
  tableId,
  fields,
  relationships,
  tables,
  items,
  total,
  page,
  pageSize,
  search,
  sortBy,
  sortDir,
  onDataChange,
  onSearchChange,
  onPageChange,
  onSortChange,
}: Props) {
  const [formOpen, setFormOpen] = useState(false)
  const [editingItem, setEditingItem] = useState<Item | null>(null)
  const [hiddenCols, setHiddenCols] = useState<Set<string>>(new Set())
  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  useEffect(() => {
    const stored = localStorage.getItem(`hiddenCols_${tableId}`)
    if (stored) {
      try {
        setHiddenCols(new Set(JSON.parse(stored)))
      } catch {}
    }
  }, [tableId])

  const toggleCol = (name: string) => {
    const next = new Set(hiddenCols)
    if (next.has(name)) {
      next.delete(name)
    } else {
      next.add(name)
    }
    setHiddenCols(next)
    localStorage.setItem(`hiddenCols_${tableId}`, JSON.stringify([...next]))
  }

  const handleSort = (fieldName: string) => {
    onSortChange(fieldName)
  }

  const handleCreate = () => {
    setEditingItem(null)
    setFormOpen(true)
  }

  const handleEdit = (item: Item) => {
    setEditingItem(item)
    setFormOpen(true)
  }

  const handleDelete = async (id: number) => {
    if (!confirm("Delete this item?")) return
    await api.deleteItem(tableId, id)
    onDataChange()
  }

  const handleSave = async (owner: string, data: Record<string, any>) => {
    if (editingItem) {
      await api.updateItem(tableId, editingItem.id, { owner, data })
    } else {
      await api.createItem(tableId, { owner, data })
    }
    onDataChange()
  }

  const SortIcon = ({ field }: { field: string }) => {
    if (sortBy !== field) return <ArrowUpDown className="ml-1 h-3 w-3 inline opacity-30" />
    return (
      <span className="ml-1 inline text-xs font-bold">
        {sortDir === "asc" ? "\u2191" : "\u2193"}
      </span>
    )
  }

  const formatValue = (val: any) => {
    if (val == null) return "-"
    return String(val)
  }

  const renderRelValue = (rel: Relationship, item: Item) => {
    const rv = item.relationships?.[rel.rel_name] as RelValue | undefined
    if (!rv) return "-"

    if ("item_id" in rv) {
      return rv.label || (rv.item_id != null ? `#${rv.item_id}` : "-")
    }
    if ("items" in rv) {
      if (rv.items.length === 0) return "-"
      return rv.items.map((i) => i.label || `#${i.item_id}`).join(", ")
    }
    return "-"
  }

  const fromRels = relationships.filter((r) => r.from_table_id === tableId)
  const visibleFields = fields.filter((f) => !hiddenCols.has(f.field_name))
  const visibleRels = fromRels.filter((r) => !hiddenCols.has(r.rel_name))

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <Input
          placeholder="Search..."
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          className="max-w-sm"
        />
        <div className="flex gap-2">
          <Dialog>
            <DialogTrigger asChild>
              <Button variant="outline" size="sm">
                <Columns3 className="h-4 w-4 mr-1" /> Columns
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-xs">
              <DialogHeader>
                <DialogTitle>Visible Columns</DialogTitle>
              </DialogHeader>
              <div className="space-y-2 max-h-60 overflow-y-auto">
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={!hiddenCols.has("id")}
                    onChange={() => toggleCol("id")}
                  />
                  ID
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={!hiddenCols.has("owner")}
                    onChange={() => toggleCol("owner")}
                  />
                  Owner
                </label>
                {fields.map((f) => (
                  <label key={f.id} className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={!hiddenCols.has(f.field_name)}
                      onChange={() => toggleCol(f.field_name)}
                    />
                    {f.field_label}
                  </label>
                ))}
                {fromRels.map((r) => (
                  <label key={r.id} className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={!hiddenCols.has(r.rel_name)}
                      onChange={() => toggleCol(r.rel_name)}
                    />
                    {r.rel_label || r.rel_name}
                  </label>
                ))}
              </div>
            </DialogContent>
          </Dialog>
          <Button onClick={handleCreate}>+ New Item</Button>
        </div>
      </div>

      <div className="rounded-md border">
        <UiTable>
          <TableHeader>
            <TableRow>
              {!hiddenCols.has("id") && (
                <TableHead className="cursor-pointer select-none w-16" onClick={() => handleSort("id")}>
                  ID <SortIcon field="id" />
                </TableHead>
              )}
              {!hiddenCols.has("owner") && (
                <TableHead className="cursor-pointer select-none" onClick={() => handleSort("owner")}>
                  Owner <SortIcon field="owner" />
                </TableHead>
              )}
              {visibleFields.map((f) => (
                <TableHead
                  key={f.id}
                  className="cursor-pointer select-none"
                  onClick={() => handleSort(f.field_name)}
                >
                  {f.field_label} <SortIcon field={f.field_name} />
                </TableHead>
              ))}
              {visibleRels.map((r) => (
                <TableHead key={r.id} className="select-none">
                  <Link2 className="h-3 w-3 inline mr-1 opacity-50" />
                  {r.rel_label || r.rel_name}
                </TableHead>
              ))}
              {!hiddenCols.has("created_at") && (
                <TableHead className="cursor-pointer select-none" onClick={() => handleSort("created_at")}>
                  Created <SortIcon field="created_at" />
                </TableHead>
              )}
              {!hiddenCols.has("updated_at") && (
                <TableHead className="cursor-pointer select-none" onClick={() => handleSort("updated_at")}>
                  Updated <SortIcon field="updated_at" />
                </TableHead>
              )}
              <TableHead className="w-24">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={3 + visibleFields.length + visibleRels.length}
                  className="text-center h-24 text-muted-foreground"
                >
                  No items found.
                </TableCell>
              </TableRow>
            ) : (
              items.map((item) => (
                <TableRow key={item.id}>
                  {!hiddenCols.has("id") && (
                    <TableCell className="font-mono text-xs">{item.id}</TableCell>
                  )}
                  {!hiddenCols.has("owner") && (
                    <TableCell>{item.owner}</TableCell>
                  )}
                  {visibleFields.map((f) => (
                    <TableCell key={f.id}>
                      {formatValue(item.fields[f.field_name])}
                    </TableCell>
                  ))}
                  {visibleRels.map((r) => (
                    <TableCell key={r.id} className="text-sm">
                      {renderRelValue(r, item)}
                    </TableCell>
                  ))}
                  {!hiddenCols.has("created_at") && (
                    <TableCell className="text-xs text-muted-foreground">{item.created_at}</TableCell>
                  )}
                  {!hiddenCols.has("updated_at") && (
                    <TableCell className="text-xs text-muted-foreground">{item.updated_at}</TableCell>
                  )}
                  <TableCell>
                    <div className="flex gap-1">
                      <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => handleEdit(item)}>
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive" onClick={() => handleDelete(item.id)}>
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </UiTable>
      </div>

      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">
          {total} total items · Page {page} of {totalPages}
        </span>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
            Previous
          </Button>
          <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => onPageChange(page + 1)}>
            Next
          </Button>
        </div>
      </div>

      <ItemForm
        open={formOpen}
        onClose={() => setFormOpen(false)}
        onSave={handleSave}
        tableId={tableId}
        fields={fields}
        relationships={relationships}
        item={editingItem}
      />
    </div>
  )
}
