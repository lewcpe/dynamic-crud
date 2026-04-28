import { useState, useEffect } from "react"
import { api } from "../api"
import type { User } from "../types"
import { Button } from "@/components/ui/button"
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
import { Users, Shield, ShieldOff, Trash2 } from "lucide-react"

interface Props {
  onChange: () => void
}

export default function UserManager({ onChange }: Props) {
  const [open, setOpen] = useState(false)
  const [users, setUsers] = useState<User[]>([])

  useEffect(() => {
    if (open) loadUsers()
  }, [open])

  const loadUsers = async () => {
    const u = await api.listUsers()
    setUsers(u)
  }

  const handleToggleAdmin = async (user: User) => {
    if (user.role === "admin") {
      await api.removeAdmin(user.id)
    } else {
      await api.makeAdmin(user.id)
    }
    loadUsers()
    onChange()
  }

  const handleDelete = async (user: User) => {
    if (!confirm(`Delete user ${user.email}?`)) return
    await api.deleteUser(user.id)
    loadUsers()
    onChange()
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          <Users className="h-4 w-4 mr-1" /> Users
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Manage Users</DialogTitle>
        </DialogHeader>
        <div className="space-y-2 max-h-96 overflow-y-auto">
          {users.map((u) => (
            <div key={u.id} className="flex items-center justify-between rounded bg-muted/50 px-3 py-2 text-sm">
              <div>
                <span className="font-medium">{u.name || u.email}</span>
                <span className="ml-2 text-muted-foreground">({u.email})</span>
                <span className={`ml-2 px-1.5 py-0.5 rounded text-xs ${u.role === "admin" ? "bg-primary text-primary-foreground" : "bg-secondary text-secondary-foreground"}`}>
                  {u.role}
                </span>
              </div>
              <div className="flex gap-1">
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  onClick={() => handleToggleAdmin(u)}
                  title={u.role === "admin" ? "Remove admin" : "Make admin"}
                >
                  {u.role === "admin" ? <ShieldOff className="h-4 w-4" /> : <Shield className="h-4 w-4" />}
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 text-destructive"
                  onClick={() => handleDelete(u)}
                  title="Delete user"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
          ))}
          {users.length === 0 && (
            <p className="text-sm text-muted-foreground text-center py-4">No users found.</p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
