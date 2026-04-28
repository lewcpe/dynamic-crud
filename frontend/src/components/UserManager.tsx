import { useState, useEffect, useCallback } from "react"
import { api } from "../api"
import type { User } from "../types"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Users, Shield, ShieldOff, Trash2, UserCog } from "lucide-react"
import SearchSelect from "./SearchSelect"

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

  const handleSetManager = async (userId: number, managerId: number | null) => {
    await api.setManager(userId, managerId)
    loadUsers()
    onChange()
  }

  const fetchManagerOptions = useCallback(async (q: string, excludeId: number) => {
    const results = await api.listSystemUsers(q, 20)
    return results.filter((u) => u.id !== excludeId)
  }, [])

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          <Users className="h-4 w-4 mr-1" /> Users
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>Manage Users</DialogTitle>
        </DialogHeader>
        <div className="space-y-2 max-h-96 overflow-y-auto">
          {users.map((u) => (
            <div key={u.id} className="rounded bg-muted/50 px-3 py-2 text-sm">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{u.name || u.email}</span>
                  <span className="text-muted-foreground">({u.email})</span>
                  <span className={`px-1.5 py-0.5 rounded text-xs ${u.role === "admin" ? "bg-primary text-primary-foreground" : "bg-secondary text-secondary-foreground"}`}>
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
              <div className="mt-2 flex items-center gap-2">
                <UserCog className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                <span className="text-xs text-muted-foreground shrink-0">Manager:</span>
                <div className="flex-1 min-w-0">
                  <SearchSelect
                    value={u.manager_id}
                    onChange={(id) => handleSetManager(u.id, id)}
                    fetchOptions={(q) => fetchManagerOptions(q, u.id)}
                    placeholder="None"
                  />
                </div>
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
