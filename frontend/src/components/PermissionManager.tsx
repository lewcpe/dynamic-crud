import { useState, useEffect, useCallback } from "react"
import { api } from "../api"
import type { Permission, User, Group } from "../types"
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
import { X, Plus, Shield } from "lucide-react"
import SearchSelect from "./SearchSelect"

interface Props {
  tableId: number
  onChange: () => void
}

const TARGET_TYPES = [
  { value: "role", label: "Role" },
  { value: "user", label: "User" },
  { value: "group", label: "Group" },
]

const ACTIONS = ["list", "view", "create", "update", "delete"]

export default function PermissionManager({ tableId, onChange }: Props) {
  const [open, setOpen] = useState(false)
  const [perms, setPerms] = useState<Permission[]>([])
  const [users, setUsers] = useState<User[]>([])
  const [groups, setGroups] = useState<Group[]>([])
  const [error, setError] = useState("")

  const [targetType, setTargetType] = useState("role")
  const [targetId, setTargetId] = useState<number | null>(null)
  const [targetRole, setTargetRole] = useState("user")
  const [rules, setRules] = useState<Record<string, string>>({
    list: "", view: "", create: "", update: "", delete: "",
  })

  useEffect(() => {
    if (open) {
      loadPerms()
      api.listUsers().then(setUsers).catch(() => {})
      api.listGroups().then(setGroups).catch(() => {})
    }
  }, [open, tableId])

  const loadPerms = async () => {
    const p = await api.listPermissions(tableId)
    setPerms(p)
  }

  const fetchUserOptions = useCallback(async (q: string) => {
    return api.listSystemUsers(q, 20)
  }, [])

  const fetchGroupOptions = useCallback(async (q: string) => {
    return api.listSystemGroups(q, 20)
  }, [])

  const handleAdd = async () => {
    setError("")
    try {
      const data: any = {
        target_type: targetType,
        list_rule: rules.list || null,
        view_rule: rules.view || null,
        create_rule: rules.create || null,
        update_rule: rules.update || null,
        delete_rule: rules.delete || null,
      }
      if (targetType === "role") data.target_role = targetRole
      if (targetType === "user" || targetType === "group") data.target_id = targetId

      await api.createPermission(tableId, data)
      setTargetType("role")
      setTargetId(null)
      setTargetRole("user")
      setRules({ list: "", view: "", create: "", update: "", delete: "" })
      loadPerms()
      onChange()
    } catch (e: any) {
      setError(e.message)
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm("Delete this permission?")) return
    await api.deletePermission(tableId, id)
    loadPerms()
    onChange()
  }

  const getTargetLabel = (p: Permission) => {
    if (p.target_type === "role") return `Role: ${p.target_role}`
    if (p.target_type === "user") {
      const u = users.find((u) => u.id === p.target_id)
      return `User: ${u?.email || `#${p.target_id}`}`
    }
    if (p.target_type === "group") {
      const g = groups.find((g) => g.id === p.target_id)
      return `Group: ${g?.name || `#${p.target_id}`}`
    }
    return p.target_type
  }

  const getRuleLabel = (rule: string | null) => {
    if (rule === null) return "locked"
    if (rule === "") return "open"
    return rule
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          <Shield className="h-4 w-4 mr-1" /> Permissions
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Manage Permissions</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2 max-h-48 overflow-y-auto">
            {perms.map((p) => (
              <div key={p.id} className="flex items-center justify-between rounded bg-muted/50 px-3 py-2 text-sm">
                <div className="flex-1">
                  <span className="font-medium">{getTargetLabel(p)}</span>
                  <div className="flex gap-2 mt-1 text-xs text-muted-foreground">
                    {ACTIONS.map((a) => (
                      <span key={a} className={`px-1.5 py-0.5 rounded ${p[`${a}_rule` as keyof Permission] === null ? "bg-red-100 text-red-700" : p[`${a}_rule` as keyof Permission] === "" ? "bg-green-100 text-green-700" : "bg-blue-100 text-blue-700"}`}>
                        {a}: {getRuleLabel(p[`${a}_rule` as keyof Permission] as string | null)}
                      </span>
                    ))}
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 text-destructive"
                  onClick={() => handleDelete(p.id)}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            ))}
            {perms.length === 0 && (
              <p className="text-sm text-muted-foreground">No permissions set. All access is open by default.</p>
            )}
          </div>

          <div className="border-t pt-4 space-y-3">
            <div className="grid grid-cols-3 gap-3">
              <div className="space-y-1.5">
                <Label>Target Type</Label>
                <Select value={targetType} onValueChange={(v) => { setTargetType(v); setTargetId(null) }}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {TARGET_TYPES.map((t) => (
                      <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              {targetType === "role" && (
                <div className="space-y-1.5">
                  <Label>Target Role</Label>
                  <Select value={targetRole} onValueChange={setTargetRole}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="user">User</SelectItem>
                      <SelectItem value="guest">Guest</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              )}
              {targetType === "user" && (
                <div className="space-y-1.5">
                  <Label>Target User</Label>
                  <SearchSelect
                    value={targetId}
                    onChange={setTargetId}
                    fetchOptions={fetchUserOptions}
                    placeholder="Search users..."
                  />
                </div>
              )}
              {targetType === "group" && (
                <div className="space-y-1.5">
                  <Label>Target Group</Label>
                  <SearchSelect
                    value={targetId}
                    onChange={setTargetId}
                    fetchOptions={fetchGroupOptions}
                    placeholder="Search groups..."
                  />
                </div>
              )}
            </div>

            <div className="grid grid-cols-5 gap-2">
              {ACTIONS.map((a) => (
                <div key={a} className="space-y-1">
                  <Label className="text-xs capitalize">{a}</Label>
                  <Select
                    value={rules[a] === null ? "locked" : rules[a] === "" ? "open" : "custom"}
                    onValueChange={(v) => {
                      const newRules = { ...rules }
                      if (v === "locked") newRules[a] = null as any
                      else if (v === "open") newRules[a] = ""
                      else newRules[a] = rules[a] || '@request.auth.id != ""'
                      setRules(newRules)
                    }}
                  >
                    <SelectTrigger className="h-8 text-xs"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="open">Open</SelectItem>
                      <SelectItem value="locked">Locked</SelectItem>
                      <SelectItem value="custom">Rule</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              ))}
            </div>

            {ACTIONS.some((a) => rules[a] !== null && rules[a] !== "") && (
              <div className="space-y-2">
                {ACTIONS.filter((a) => rules[a] !== null && rules[a] !== "").map((a) => (
                  <div key={a} className="flex items-center gap-2">
                    <Label className="text-xs w-16 capitalize">{a}</Label>
                    <Input
                      className="text-xs font-mono"
                      value={rules[a]}
                      onChange={(e) => setRules({ ...rules, [a]: e.target.value })}
                      placeholder='e.g. status = "active" && owner = "me"'
                    />
                  </div>
                ))}
              </div>
            )}

            {error && <p className="text-sm text-destructive">{error}</p>}
            <Button onClick={handleAdd} className="w-full" size="sm">
              <Plus className="h-4 w-4 mr-1" /> Add Permission
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
