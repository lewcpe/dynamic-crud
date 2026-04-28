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
import { X, Plus } from "lucide-react"

interface Props {
  tables: Table[]
  onChange: () => void
}

export default function TableManager({ tables, onChange }: Props) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState("")
  const [label, setLabel] = useState("")
  const [error, setError] = useState("")

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
      await api.createTable({ name: name.trim(), label: label.trim() || name.trim() })
      setName("")
      setLabel("")
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

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          Manage Tables
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Manage Tables</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2 max-h-48 overflow-y-auto">
            {tables.map((t) => (
              <div key={t.id} className="flex items-center justify-between rounded bg-muted/50 px-3 py-2 text-sm">
                <div>
                  <span className="font-medium">{t.label || t.name}</span>
                  {t.label && t.label !== t.name && (
                    <span className="ml-2 text-muted-foreground">({t.name})</span>
                  )}
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 text-destructive"
                  onClick={() => handleDelete(t.id)}
                >
                  <X className="h-4 w-4" />
                </Button>
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
