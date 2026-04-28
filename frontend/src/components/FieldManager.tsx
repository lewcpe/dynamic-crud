import { useState } from "react"
import { api } from "../api"
import type { Field } from "../types"
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
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { X, Plus } from "lucide-react"

const FIELD_TYPES = [
  { value: "text", label: "Text" },
  { value: "int", label: "Integer" },
  { value: "float", label: "Float" },
  { value: "date", label: "Date" },
  { value: "datetime", label: "DateTime" },
]

interface Props {
  tableId: number
  fields: Field[]
  onChange: () => void
}

export default function FieldManager({ tableId, fields, onChange }: Props) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState("")
  const [type, setType] = useState("text")
  const [label, setLabel] = useState("")
  const [error, setError] = useState("")

  const handleAdd = async () => {
    setError("")
    if (!name.trim()) {
      setError("Field name is required")
      return
    }
    if (!/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(name.trim())) {
      setError("Field name must start with a letter/underscore and contain only letters, digits, underscores")
      return
    }
    try {
      await api.createField(tableId, {
        field_name: name.trim(),
        field_type: type,
        field_label: label.trim() || name.trim(),
      })
      setName("")
      setType("text")
      setLabel("")
      onChange()
    } catch (e: any) {
      setError(e.message)
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm("Delete this field? Data in this column will be lost.")) return
    await api.deleteField(tableId, id)
    onChange()
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          Manage Fields ({fields.length})
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Manage Fields</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          {/* current fields */}
          <div className="space-y-2 max-h-48 overflow-y-auto">
            {fields.map((f) => (
              <div key={f.id} className="flex items-center justify-between rounded bg-muted/50 px-3 py-2 text-sm">
                <div>
                  <span className="font-medium">{f.field_label}</span>
                  <span className="ml-2 text-muted-foreground">({f.field_name} / {f.field_type})</span>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 text-destructive"
                  onClick={() => handleDelete(f.id)}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            ))}
            {fields.length === 0 && (
              <p className="text-sm text-muted-foreground">No custom fields yet. Add one below.</p>
            )}
          </div>

          {/* add new */}
          <div className="border-t pt-4 space-y-3">
            <div className="space-y-1.5">
              <Label>Field Name</Label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. status, priority"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Type</Label>
                <Select value={type} onValueChange={setType}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {FIELD_TYPES.map((t) => (
                      <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Display Label</Label>
                <Input
                  value={label}
                  onChange={(e) => setLabel(e.target.value)}
                  placeholder={name || "Label"}
                />
              </div>
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <Button onClick={handleAdd} className="w-full" size="sm">
              <Plus className="h-4 w-4 mr-1" /> Add Field
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
