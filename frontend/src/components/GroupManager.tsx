import { useState, useEffect } from "react"
import { api } from "../api"
import type { Group, User } from "../types"
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
import { X, Plus, UsersRound } from "lucide-react"

interface Props {
  onChange: () => void
}

export default function GroupManager({ onChange }: Props) {
  const [open, setOpen] = useState(false)
  const [groups, setGroups] = useState<Group[]>([])
  const [members, setMembers] = useState<Record<number, User[]>>({})
  const [expandedGroup, setExpandedGroup] = useState<number | null>(null)
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [error, setError] = useState("")
  const [allUsers, setAllUsers] = useState<User[]>([])
  const [addUserId, setAddUserId] = useState("")

  useEffect(() => {
    if (open) loadGroups()
  }, [open])

  const loadGroups = async () => {
    const g = await api.listGroups()
    setGroups(g)
    api.listUsers().then(setAllUsers).catch(() => {})
  }

  const loadMembers = async (groupId: number) => {
    const m = await api.listGroupMembers(groupId)
    setMembers((prev) => ({ ...prev, [groupId]: m }))
  }

  const handleAdd = async () => {
    setError("")
    if (!name.trim()) {
      setError("Group name is required")
      return
    }
    try {
      await api.createGroup({ name: name.trim(), description: description.trim() })
      setName("")
      setDescription("")
      loadGroups()
      onChange()
    } catch (e: any) {
      setError(e.message)
    }
  }

  const handleDelete = async (group: Group) => {
    if (!confirm(`Delete group "${group.name}"?`)) return
    await api.deleteGroup(group.id)
    loadGroups()
    onChange()
  }

  const handleToggleExpand = (groupId: number) => {
    if (expandedGroup === groupId) {
      setExpandedGroup(null)
    } else {
      setExpandedGroup(groupId)
      loadMembers(groupId)
    }
  }

  const handleAddMember = async (groupId: number) => {
    if (!addUserId) return
    await api.addGroupMember(groupId, Number(addUserId))
    setAddUserId("")
    loadMembers(groupId)
    onChange()
  }

  const handleRemoveMember = async (groupId: number, userId: number) => {
    await api.removeGroupMember(groupId, userId)
    loadMembers(groupId)
    onChange()
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          <UsersRound className="h-4 w-4 mr-1" /> Groups
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Manage Groups</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2 max-h-48 overflow-y-auto">
            {groups.map((g) => (
              <div key={g.id} className="rounded bg-muted/50 px-3 py-2 text-sm">
                <div className="flex items-center justify-between">
                  <button
                    className="font-medium hover:underline text-left"
                    onClick={() => handleToggleExpand(g.id)}
                  >
                    {g.name}
                    {g.description && <span className="ml-2 text-muted-foreground">({g.description})</span>}
                  </button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 text-destructive"
                    onClick={() => handleDelete(g)}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
                {expandedGroup === g.id && (
                  <div className="mt-2 pl-2 border-l-2 space-y-2">
                    {(members[g.id] || []).map((m) => (
                      <div key={m.id} className="flex items-center justify-between text-xs">
                        <span>{m.name || m.email}</span>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-6 w-6 text-destructive"
                          onClick={() => handleRemoveMember(g.id, m.id)}
                        >
                          <X className="h-3 w-3" />
                        </Button>
                      </div>
                    ))}
                    {(members[g.id] || []).length === 0 && (
                      <p className="text-xs text-muted-foreground">No members</p>
                    )}
                    <div className="flex gap-1">
                      <select
                        className="flex-1 border rounded px-2 py-1 text-xs"
                        value={addUserId}
                        onChange={(e) => setAddUserId(e.target.value)}
                      >
                        <option value="">Add user...</option>
                        {allUsers
                          .filter((u) => !(members[g.id] || []).some((m) => m.id === u.id))
                          .map((u) => (
                            <option key={u.id} value={u.id}>{u.name || u.email}</option>
                          ))}
                      </select>
                      <Button size="sm" className="h-6 text-xs" onClick={() => handleAddMember(g.id)}>
                        <Plus className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            ))}
            {groups.length === 0 && (
              <p className="text-sm text-muted-foreground">No groups yet.</p>
            )}
          </div>

          <div className="border-t pt-4 space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Name</Label>
                <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="editors" />
              </div>
              <div className="space-y-1.5">
                <Label>Description</Label>
                <Input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Editors group" />
              </div>
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <Button onClick={handleAdd} className="w-full" size="sm">
              <Plus className="h-4 w-4 mr-1" /> Add Group
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
