import { useState, useEffect } from "react"
import type { Field, Item } from "../types"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

interface Props {
  open: boolean
  onClose: () => void
  onSave: (owner: string, data: Record<string, any>) => Promise<void>
  fields: Field[]
  item?: Item | null
}

export default function ItemForm({ open, onClose, onSave, fields, item }: Props) {
  const [owner, setOwner] = useState("default")
  const [values, setValues] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState("")

  useEffect(() => {
    if (open) {
      setOwner(item?.owner || "default")
      const init: Record<string, string> = {}
      fields.forEach((f) => {
        init[f.field_name] = item?.fields?.[f.field_name] != null ? String(item.fields[f.field_name]) : ""
      })
      setValues(init)
      setError("")
    }
  }, [open, item, fields])

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
      onClose()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  const title = item ? "Edit Item" : "Create Item"

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose() }}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
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
              {(f.field_type === "date") && (
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
          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSubmit} disabled={saving}>
            {saving ? "Saving..." : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
