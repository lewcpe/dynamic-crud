import { useState, useEffect, useCallback } from "react"
import { api } from "../api"
import type { Field, Item, Relationship, RelValue, User } from "../types"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetFooter,
} from "@/components/ui/sheet"
import SearchSelect from "./SearchSelect"
import SearchMultiSelect from "./SearchMultiSelect"

interface Props {
  open: boolean
  onClose: () => void
  onSave: (owner: string, data: Record<string, any>) => Promise<Item>
  onSaved: () => void
  tableId: number
  fields: Field[]
  relationships: Relationship[]
  user: User
  item?: Item | null
}

export default function ItemForm({ open, onClose, onSave, onSaved, tableId, fields, relationships, user, item }: Props) {
  const [owner, setOwner] = useState(user.name || user.email)
  const [ownerId, setOwnerId] = useState<number | null>(user.id)
  const [values, setValues] = useState<Record<string, string>>({})
  const [relValues, setRelValues] = useState<Record<string, number | number[]>>({})
  const [reverseRelValues, setReverseRelValues] = useState<Record<string, number[]>>({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState("")

  const fromRels = relationships.filter((r) => r.from_table_id === tableId)
  const toRels = relationships.filter((r) => r.to_table_id === tableId && r.from_table_id !== tableId)
  const isAdmin = user.role === "admin"

  useEffect(() => {
    if (open) {
      if (item) {
        setOwner(item.owner)
      } else {
        setOwner(user.name || user.email)
        setOwnerId(user.id)
      }
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

      const initReverse: Record<string, number[]> = {}
      toRels.forEach((r) => {
        const rv = item?.relationships?.[r.rel_name] as RelValue | undefined
        if (rv && "items" in rv) {
          initReverse[`to_${r.id}`] = rv.items.map((i) => i.item_id)
        } else {
          initReverse[`to_${r.id}`] = []
        }
      })
      setReverseRelValues(initReverse)
      setError("")
    }
  }, [open, item, fields, relationships])

  const fetchUserOptions = useCallback(async (q: string) => {
    return api.listSystemUsers(q, 20)
  }, [])

  const fetchTableOptions = useCallback(async (tableId: number, q: string) => {
    return api.listItemOptions(tableId, q, 20)
  }, [])

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

      const savedItem = await onSave(owner, data)
      const itemId = savedItem?.id || item?.id

      if (itemId) {
        for (const r of fromRels) {
          const val = relValues[r.rel_name]
          if (r.rel_type === "n-n") {
            await api.setRelationshipLinks(tableId, r.id, {
              item_id: itemId,
              target_ids: Array.isArray(val) ? val : [],
            })
          } else if (val && typeof val === "number" && val > 0) {
            await api.setRelationshipLinks(tableId, r.id, {
              item_id: itemId,
              target_ids: [val],
            })
          }
        }

        for (const r of toRels) {
          const val = reverseRelValues[`to_${r.id}`] || []
          await api.setRelationshipLinks(tableId, r.id, {
            item_id: itemId,
            target_ids: val,
          })
        }
      }

      onSaved()
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
            {isAdmin ? (
              <SearchSelect
                value={ownerId}
                onChange={(id) => {
                  setOwnerId(id)
                }}
                fetchOptions={fetchUserOptions}
                placeholder="Select owner..."
              />
            ) : (
              <Input id="owner" value={owner} readOnly className="bg-muted" />
            )}
          </div>

          {fields.map((f) => (
            <div key={f.id} className="space-y-1.5">
              <Label htmlFor={f.field_name}>{f.field_label}</Label>
              {f.field_type === "text" && (
                <Input id={f.field_name} value={values[f.field_name] || ""} onChange={(e) => setValues({ ...values, [f.field_name]: e.target.value })} />
              )}
              {f.field_type === "int" && (
                <Input id={f.field_name} type="number" step="1" value={values[f.field_name] || ""} onChange={(e) => setValues({ ...values, [f.field_name]: e.target.value })} />
              )}
              {f.field_type === "float" && (
                <Input id={f.field_name} type="number" step="any" value={values[f.field_name] || ""} onChange={(e) => setValues({ ...values, [f.field_name]: e.target.value })} />
              )}
              {f.field_type === "date" && (
                <Input id={f.field_name} type="date" value={values[f.field_name] || ""} onChange={(e) => setValues({ ...values, [f.field_name]: e.target.value })} />
              )}
              {f.field_type === "datetime" && (
                <Input id={f.field_name} type="datetime-local" value={values[f.field_name] || ""} onChange={(e) => setValues({ ...values, [f.field_name]: e.target.value })} />
              )}
            </div>
          ))}

          {/* Forward relationships */}
          {fromRels.length > 0 && (
            <div className="border-t pt-4 space-y-4">
              <h3 className="text-sm font-medium">Relationships</h3>
              {fromRels.map((r) => (
                <div key={r.id} className="space-y-1.5">
                  <Label>{r.rel_label || r.rel_name}</Label>
                  {r.rel_type === "n-n" ? (
                    <SearchMultiSelect
                      value={Array.isArray(relValues[r.rel_name]) ? (relValues[r.rel_name] as number[]) : []}
                      onChange={(ids) => setRelValues({ ...relValues, [r.rel_name]: ids })}
                      fetchOptions={(q) => r.to_system_table ? api.listSystemUsers(q, 20) : fetchTableOptions(r.to_table_id!, q)}
                      placeholder="Search..."
                    />
                  ) : (
                    <SearchSelect
                      value={(() => {
                        const v = relValues[r.rel_name]
                        return typeof v === "number" && v > 0 ? v : null
                      })()}
                      onChange={(id) => setRelValues({ ...relValues, [r.rel_name]: id || 0 })}
                      fetchOptions={(q) => r.to_system_table ? api.listSystemUsers(q, 20) : fetchTableOptions(r.to_table_id!, q)}
                      placeholder="Select..."
                    />
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Reverse relationships */}
          {toRels.length > 0 && (
            <div className="border-t pt-4 space-y-4">
              <h3 className="text-sm font-medium">Related From</h3>
              {toRels.map((r) => (
                <div key={r.id} className="space-y-1.5">
                  <Label className="text-muted-foreground">
                    {r.from_label || r.rel_label || r.rel_name}
                  </Label>
                  <SearchMultiSelect
                    value={reverseRelValues[`to_${r.id}`] || []}
                    onChange={(ids) => setReverseRelValues({ ...reverseRelValues, [`to_${r.id}`]: ids })}
                    fetchOptions={(q) => fetchTableOptions(r.from_table_id, q)}
                    placeholder="Search..."
                  />
                </div>
              ))}
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
