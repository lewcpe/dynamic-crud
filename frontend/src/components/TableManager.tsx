import { useState } from "react"
import { api } from "../api"
import type { Table } from "../types"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { X, Plus, Settings, RefreshCw } from "lucide-react"

interface Props {
  tables: Table[]
  onChange: () => void
}

export default function TableManager({ tables, onChange }: Props) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState("")
  const [label, setLabel] = useState("")
  const [represent, setRepresent] = useState("")
  const [editId, setEditId] = useState<number | null>(null)
  const [editRepresent, setEditRepresent] = useState("")
  const [error, setError] = useState("")
  const [refreshing, setRefreshing] = useState<number | null>(null)

  const handleAdd = async () => {
    setError("")
    if (!name.trim()) {
      setError("Table name is required")
      return
    }
    if (!/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(name.trim())) {
      setError("Name must start with a letter/underscore and contain only letters, digits, underscores")
      return
    }
    try {
      await api.createTable({ name: name.trim(), label: label.trim() || name.trim(), represent: represent.trim() })
      setName("")
      setLabel("")
      setRepresent("")
      onChange()
    } catch (e: any) {
      setError(e.message)
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm("Delete this table and all its data?")) return
    await api.deleteTable(id)
    onChange()
  }

  const handleEditRepresent = (t: Table) => {
    setEditId(t.id)
    setEditRepresent(t.represent || "")
  }

  const handleSaveRepresent = async () => {
    if (editId == null) return
    await api.updateTable(editId, { represent: editRepresent })
    setEditId(null)
    setEditRepresent("")
    onChange()
  }

  const handleRefreshRepresent = async (t: Table) => {
    setRefreshing(t.id)
    // Re-save the represent expression to trigger a refresh
    await api.updateTable(t.id, { represent: t.represent || "" })
    onChange()
    setTimeout(() => setRefreshing(null), 500)
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          Manage Tables
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Manage Tables</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2 max-h-60 overflow-y-auto">
            {tables.map((t) => (
              <div key={t.id} className="rounded bg-muted/50 px-3 py-2 text-sm">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="font-medium">{t.label || t.name}</span>
                    {t.label && t.label !== t.name && (
                      <span className="ml-2 text-muted-foreground">({t.name})</span>
                    )}
                  </div>
                  <div className="flex gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      onClick={() => handleEditRepresent(t)}
                      title="Edit represent expression"
                    >
                      <Settings className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className={`h-7 w-7 ${refreshing === t.id ? "animate-spin" : ""}`}
                      onClick={() => handleRefreshRepresent(t)}
                      title="Refresh represent text"
                    >
                      <RefreshCw className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 text-destructive"
                      onClick={() => handleDelete(t.id)}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
                {t.represent && (
                  <div className="text-xs text-muted-foreground mt-1">
                    Represent: <code className="bg-muted px-1 rounded">{t.represent}</code>
                  </div>
                )}
                {editId === t.id && (
                  <div className="mt-2 flex gap-2">
                    <Input
                      className="text-xs"
                      value={editRepresent}
                      onChange={(e) => setEditRepresent(e.target.value)}
                      placeholder="{field_name} or {first} {last}"
                    />
                    <Button size="sm" className="h-7 text-xs" onClick={handleSaveRepresent}>Save</Button>
                    <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={() => setEditId(null)}>Cancel</Button>
                  </div>
                )}
              </div>
            ))}
            {tables.length === 0 && (
              <p className="text-sm text-muted-foreground">No tables yet. Add one below.</p>
            )}
          </div>

          <div className="border-t pt-4 space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Name</Label>
                <Input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="contacts"
                />
              </div>
              <div className="space-y-1.5">
                <Label>Label</Label>
                <Input
                  value={label}
                  onChange={(e) => setLabel(e.target.value)}
                  placeholder={name || "Contacts"}
                />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label>Represent Expression</Label>
              <Input
                value={represent}
                onChange={(e) => setRepresent(e.target.value)}
                placeholder="{first_name} {last_name} (leave empty for auto-detect)"
              />
              <p className="text-xs text-muted-foreground">
                Use field names in curly braces. Default: first text field.
              </p>
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <Button onClick={handleAdd} className="w-full" size="sm">
              <Plus className="h-4 w-4 mr-1" /> Add Table
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
