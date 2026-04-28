import { useState } from "react"
import { api } from "../api"
import type { Table, Relationship } from "../types"
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
import { X, Plus, Link2 } from "lucide-react"

const REL_TYPES = [
  { value: "1-1", label: "One-to-One" },
  { value: "1-n", label: "One-to-Many" },
  { value: "n-n", label: "Many-to-Many" },
]

const SYSTEM_TABLES = [
  { value: "users", label: "System Users" },
  { value: "groups", label: "System Groups" },
]

interface Props {
  tableId: number
  tables: Table[]
  relationships: Relationship[]
  onChange: () => void
}

export default function RelationshipManager({ tableId, tables, relationships, onChange }: Props) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState("")
  const [label, setLabel] = useState("")
  const [relType, setRelType] = useState("1-n")
  const [targetType, setTargetType] = useState<"table" | "system">("table")
  const [toTableId, setToTableId] = useState<string>("")
  const [toSystemTable, setToSystemTable] = useState<string>("")
  const [fromLabel, setFromLabel] = useState("")
  const [toLabel, setToLabel] = useState("")
  const [error, setError] = useState("")

  const otherTables = tables.filter((t) => t.id !== tableId)

  const handleAdd = async () => {
    setError("")
    if (!name.trim()) {
      setError("Relationship name is required")
      return
    }
    if (!/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(name.trim())) {
      setError("Name must start with a letter/underscore and contain only letters, digits, underscores")
      return
    }
    if (targetType === "table" && !toTableId) {
      setError("Target table is required")
      return
    }
    if (targetType === "system" && !toSystemTable) {
      setError("System table is required")
      return
    }
    try {
      const data: any = {
        rel_name: name.trim(),
        rel_label: label.trim() || name.trim(),
        rel_type: relType,
        from_label: fromLabel.trim(),
        to_label: toLabel.trim(),
      }
      if (targetType === "table") {
        data.to_table_id = Number(toTableId)
      } else {
        data.to_system_table = toSystemTable
      }
      await api.createRelationship(tableId, data)
      setName("")
      setLabel("")
      setRelType("1-n")
      setTargetType("table")
      setToTableId("")
      setToSystemTable("")
      setFromLabel("")
      setToLabel("")
      onChange()
    } catch (e: any) {
      setError(e.message)
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm("Delete this relationship? Related links will be lost.")) return
    await api.deleteRelationship(tableId, id)
    onChange()
  }

  const getTargetLabel = (r: Relationship) => {
    if (r.to_system_table) {
      return SYSTEM_TABLES.find((s) => s.value === r.to_system_table)?.label || r.to_system_table
    }
    const t = tables.find((t) => t.id === r.to_table_id)
    return t?.label || t?.name || `#${r.to_table_id}`
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          <Link2 className="h-4 w-4 mr-1" /> Relationships ({relationships.length})
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Manage Relationships</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2 max-h-48 overflow-y-auto">
            {relationships.map((r) => (
              <div key={r.id} className="flex items-center justify-between rounded bg-muted/50 px-3 py-2 text-sm">
                <div>
                  <span className="font-medium">{r.rel_label || r.rel_name}</span>
                  <span className="ml-2 text-muted-foreground">
                    ({r.rel_type} &rarr; {getTargetLabel(r)})
                  </span>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 text-destructive"
                  onClick={() => handleDelete(r.id)}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            ))}
            {relationships.length === 0 && (
              <p className="text-sm text-muted-foreground">No relationships yet.</p>
            )}
          </div>

          <div className="border-t pt-4 space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Name</Label>
                <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="owner" />
              </div>
              <div className="space-y-1.5">
                <Label>Label</Label>
                <Input value={label} onChange={(e) => setLabel(e.target.value)} placeholder={name || "Owner"} />
              </div>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div className="space-y-1.5">
                <Label>Type</Label>
                <Select value={relType} onValueChange={setRelType}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {REL_TYPES.map((t) => (
                      <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Target</Label>
                <Select value={targetType} onValueChange={(v) => setTargetType(v as "table" | "system")}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="table">User Table</SelectItem>
                    <SelectItem value="system">System Table</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              {targetType === "table" ? (
                <div className="space-y-1.5">
                  <Label>Target Table</Label>
                  <Select value={toTableId} onValueChange={setToTableId}>
                    <SelectTrigger><SelectValue placeholder="Select..." /></SelectTrigger>
                    <SelectContent>
                      {otherTables.map((t) => (
                        <SelectItem key={t.id} value={String(t.id)}>
                          {t.label || t.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              ) : (
                <div className="space-y-1.5">
                  <Label>System Table</Label>
                  <Select value={toSystemTable} onValueChange={setToSystemTable}>
                    <SelectTrigger><SelectValue placeholder="Select..." /></SelectTrigger>
                    <SelectContent>
                      {SYSTEM_TABLES.map((s) => (
                        <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>From Label</Label>
                <Input value={fromLabel} onChange={(e) => setFromLabel(e.target.value)} placeholder="has owner" />
              </div>
              <div className="space-y-1.5">
                <Label>To Label</Label>
                <Input value={toLabel} onChange={(e) => setToLabel(e.target.value)} placeholder="owns" />
              </div>
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <Button onClick={handleAdd} className="w-full" size="sm">
              <Plus className="h-4 w-4 mr-1" /> Add Relationship
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
