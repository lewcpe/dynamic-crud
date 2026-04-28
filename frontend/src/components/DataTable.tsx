import { useState, useEffect } from "react"
import type { Field, Item, Relationship, Table, RelValue, User } from "../types"
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
  user: User
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
  user,
  onDataChange,
  onSearchChange,
  onPageChange,
  onSortChange,
}: Props) {
  const [formOpen, setFormOpen] = useState(false)
  const [editingItem, setEditingItem] = useState<Item | null>(null)
  const [hiddenCols, setHiddenCols] = useState<Set<string>>(new Set())
  const [prefsLoaded, setPrefsLoaded] = useState(false)
  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  // Load view preferences from API
  useEffect(() => {
    setPrefsLoaded(false)
    api.getViewPrefs(tableId).then((prefs) => {
      if (prefs.hidden_columns !== null) {
        // User has saved preferences
        setHiddenCols(new Set(prefs.hidden_columns))
      } else {
        // Default: hide fields beyond the first 2, hide owner
        const defaultHidden = new Set<string>()
        defaultHidden.add("owner")
        fields.forEach((f, i) => {
          if (i >= 2) defaultHidden.add(f.field_name)
        })
        setHiddenCols(defaultHidden)
      }
      setPrefsLoaded(true)
    })
  }, [tableId, fields])

  const savePrefs = (next: Set<string>) => {
    setHiddenCols(next)
    api.setViewPrefs(tableId, [...next])
  }

  const toggleCol = (name: string) => {
    const next = new Set(hiddenCols)
    if (next.has(name)) {
      next.delete(name)
    } else {
      next.add(name)
    }
    savePrefs(next)
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
    let result: Item
    if (editingItem) {
      result = await api.updateItem(tableId, editingItem.id, { owner, data })
    } else {
      result = await api.createItem(tableId, { owner, data })
    }
    return result
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

  // Forward relationships (from current table)
  const fromRels = relationships.filter((r) => r.from_table_id === tableId)
  // Reverse relationships (to current table)
  const toRels = relationships.filter((r) => r.to_table_id === tableId && r.from_table_id !== tableId)

  const getTableName = (id: number | null) => {
    if (!id) return ""
    const t = tables.find((t) => t.id === id)
    return t?.label || t?.name || ""
  }

  // Build reverse relationship display info
  const reverseRels = toRels.map((r) => ({
    ...r,
    colKey: `to_${r.id}`,
    displayLabel: r.to_label || `${getTableName(r.from_table_id)} (${r.rel_label || r.rel_name})`,
  }))

  const visibleFields = fields.filter((f) => !hiddenCols.has(f.field_name))
  const visibleRels = fromRels.filter((r) => !hiddenCols.has(r.rel_name))
  const visibleReverseRels = reverseRels.filter((r) => !hiddenCols.has(r.colKey))

  const renderReverseRelValue = (rel: typeof reverseRels[0], item: Item) => {
    const rv = item.relationships?.[rel.rel_name] as RelValue | undefined
    if (!rv) return "-"

    if ("items" in rv) {
      if (rv.items.length === 0) return "-"
      return rv.items.map((i) => i.label || `#${i.item_id}`).join(", ")
    }
    if ("item_id" in rv) {
      return rv.label || (rv.item_id != null ? `#${rv.item_id}` : "-")
    }
    return "-"
  }

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
                {fromRels.length > 0 && (
                  <div className="border-t pt-2 mt-2">
                    <p className="text-xs font-medium text-muted-foreground mb-1">Relationships</p>
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
                )}
                {reverseRels.length > 0 && (
                  <div className="border-t pt-2 mt-2">
                    <p className="text-xs font-medium text-muted-foreground mb-1">Related From</p>
                    {reverseRels.map((r) => (
                      <label key={r.colKey} className="flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={!hiddenCols.has(r.colKey)}
                          onChange={() => toggleCol(r.colKey)}
                        />
                        {r.displayLabel}
                      </label>
                    ))}
                  </div>
                )}
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
              {visibleReverseRels.map((r) => (
                <TableHead key={r.colKey} className="select-none text-muted-foreground">
                  <Link2 className="h-3 w-3 inline mr-1 opacity-30" />
                  {r.displayLabel}
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
                  colSpan={3 + visibleFields.length + visibleRels.length + visibleReverseRels.length}
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
                  {visibleReverseRels.map((r) => (
                    <TableCell key={r.colKey} className="text-sm text-muted-foreground">
                      {renderReverseRelValue(r, item)}
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
        onSaved={onDataChange}
        tableId={tableId}
        fields={fields}
        relationships={relationships}
        user={user}
        item={editingItem}
      />
    </div>
  )
}
