import { useState, useEffect } from "react"
import { api } from "../api"
import type { Field, Item, Relationship, RelValue } from "../types"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetFooter,
} from "@/components/ui/sheet"

interface Props {
  open: boolean
  onClose: () => void
  onSave: (owner: string, data: Record<string, any>) => Promise<void>
  tableId: number
  fields: Field[]
  relationships: Relationship[]
  item?: Item | null
}

export default function ItemForm({ open, onClose, onSave, tableId, fields, relationships, item }: Props) {
  const [owner, setOwner] = useState("default")
  const [values, setValues] = useState<Record<string, string>>({})
  const [relValues, setRelValues] = useState<Record<string, number | number[]>>({})
  const [systemItems, setSystemItems] = useState<Record<string, { id: number; label: string }[]>>({})
  const [tableItems, setTableItems] = useState<Record<number, { id: number; label: string }[]>>({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState("")

  const fromRels = relationships.filter((r) => r.from_table_id === tableId)

  useEffect(() => {
    if (open) {
      setOwner(item?.owner || "default")
      const init: Record<string, string> = {}
      fields.forEach((f) => {
        init[f.field_name] = item?.fields?.[f.field_name] != null ? String(item.fields[f.field_name]) : ""
      })
      setValues(init)

      const initRels: Record<string, number | number[]> = {}
      fromRels.forEach((r) => {
        const rv = item?.relationships?.[r.rel_name] as RelValue | undefined
        if (rv) {
          if ("item_id" in rv && rv.item_id != null) {
            initRels[r.rel_name] = rv.item_id
          } else if ("items" in rv) {
            initRels[r.rel_name] = rv.items.map((i) => i.item_id)
          }
        } else {
          initRels[r.rel_name] = r.rel_type === "n-n" ? [] : 0
        }
      })
      setRelValues(initRels)
      setError("")
    }
  }, [open, item, fields, relationships])

  useEffect(() => {
    if (open) {
      fromRels.forEach((r) => {
        if (r.to_system_table) {
          if (!systemItems[r.to_system_table]) {
            const fetcher = r.to_system_table === "users" ? api.listSystemUsers : api.listSystemGroups
            fetcher().then((items) => {
              setSystemItems((prev) => ({ ...prev, [r.to_system_table!]: items }))
            })
          }
        } else if (r.to_table_id && !tableItems[r.to_table_id]) {
          api.listItemOptions(r.to_table_id).then((options) => {
            setTableItems((prev) => ({
              ...prev,
              [r.to_table_id!]: options,
            }))
          })
        }
      })
    }
  }, [open, fromRels])

  const getRelOptions = (r: Relationship) => {
    if (r.to_system_table) {
      return systemItems[r.to_system_table] || []
    }
    if (r.to_table_id) {
      return tableItems[r.to_table_id] || []
    }
    return []
  }

  const handleSubmit = async () => {
    setError("")
    setSaving(true)
    try {
      const data: Record<string, any> = {}
      fields.forEach((f) => {
        const val = values[f.field_name]
        if (val === "") {
          data[f.field_name] = null
        } else if (f.field_type === "int") {
          data[f.field_name] = parseInt(val, 10)
        } else if (f.field_type === "float") {
          data[f.field_name] = parseFloat(val)
        } else {
          data[f.field_name] = val
        }
      })
      await onSave(owner, data)

      for (const r of fromRels) {
        const val = relValues[r.rel_name]
        if (r.rel_type === "n-n") {
          await api.setRelationshipLinks(tableId, r.id, {
            item_id: item?.id || 0,
            target_ids: Array.isArray(val) ? val : [],
          })
        } else if (val && typeof val === "number" && val > 0 && item?.id) {
          await api.setRelationshipLinks(tableId, r.id, {
            item_id: item.id,
            target_ids: [val],
          })
        }
      }
      onClose()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  const title = item ? "Edit Item" : "Create Item"

  return (
    <Sheet open={open} onOpenChange={(v) => { if (!v) onClose() }}>
      <SheetContent side="right" className="w-full sm:max-w-md overflow-y-auto">
        <SheetHeader>
          <SheetTitle>{title}</SheetTitle>
        </SheetHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-1.5">
            <Label htmlFor="owner">Owner</Label>
            <Input id="owner" value={owner} onChange={(e) => setOwner(e.target.value)} />
          </div>

          {fields.map((f) => (
            <div key={f.id} className="space-y-1.5">
              <Label htmlFor={f.field_name}>{f.field_label}</Label>
              {f.field_type === "text" && (
                <Input
                  id={f.field_name}
                  value={values[f.field_name] || ""}
                  onChange={(e) => setValues({ ...values, [f.field_name]: e.target.value })}
                />
              )}
              {f.field_type === "int" && (
                <Input
                  id={f.field_name}
                  type="number"
                  step="1"
                  value={values[f.field_name] || ""}
                  onChange={(e) => setValues({ ...values, [f.field_name]: e.target.value })}
                />
              )}
              {f.field_type === "float" && (
                <Input
                  id={f.field_name}
                  type="number"
                  step="any"
                  value={values[f.field_name] || ""}
                  onChange={(e) => setValues({ ...values, [f.field_name]: e.target.value })}
                />
              )}
              {f.field_type === "date" && (
                <Input
                  id={f.field_name}
                  type="date"
                  value={values[f.field_name] || ""}
                  onChange={(e) => setValues({ ...values, [f.field_name]: e.target.value })}
                />
              )}
              {f.field_type === "datetime" && (
                <Input
                  id={f.field_name}
                  type="datetime-local"
                  value={values[f.field_name] || ""}
                  onChange={(e) => setValues({ ...values, [f.field_name]: e.target.value })}
                />
              )}
            </div>
          ))}

          {fromRels.length > 0 && (
            <div className="border-t pt-4 space-y-4">
              <h3 className="text-sm font-medium">Relationships</h3>
              {fromRels.map((r) => {
                const options = getRelOptions(r)
                return (
                  <div key={r.id} className="space-y-1.5">
                    <Label>{r.rel_label || r.rel_name}</Label>
                    {r.rel_type === "n-n" ? (
                      <div className="space-y-1">
                        {options.map((opt) => (
                          <label key={opt.id} className="flex items-center gap-2 text-sm">
                            <input
                              type="checkbox"
                              checked={Array.isArray(relValues[r.rel_name]) && (relValues[r.rel_name] as number[]).includes(opt.id)}
                              onChange={(e) => {
                                const current = Array.isArray(relValues[r.rel_name]) ? [...(relValues[r.rel_name] as number[])] : []
                                if (e.target.checked) {
                                  current.push(opt.id)
                                } else {
                                  const idx = current.indexOf(opt.id)
                                  if (idx >= 0) current.splice(idx, 1)
                                }
                                setRelValues({ ...relValues, [r.rel_name]: current })
                              }}
                            />
                            {opt.label}
                          </label>
                        ))}
                      </div>
                    ) : (
                      <Select
                        value={relValues[r.rel_name] ? String(relValues[r.rel_name]) : ""}
                        onValueChange={(v) => setRelValues({ ...relValues, [r.rel_name]: Number(v) })}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Select..." />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="0">None</SelectItem>
                          {options.map((opt) => (
                            <SelectItem key={opt.id} value={String(opt.id)}>
                              {opt.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  </div>
                )
              })}
            </div>
          )}

          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>
        <SheetFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSubmit} disabled={saving}>
            {saving ? "Saving..." : "Save"}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
