import type { Table } from "../types"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

interface Props {
  tables: Table[]
  currentTableId: number | null
  onTableChange: (id: number) => void
}

export default function TableSelector({ tables, currentTableId, onTableChange }: Props) {
  if (tables.length === 0) return null

  return (
    <Select
      value={currentTableId != null ? String(currentTableId) : undefined}
      onValueChange={(v) => onTableChange(Number(v))}
    >
      <SelectTrigger className="w-48">
        <SelectValue placeholder="Select table" />
      </SelectTrigger>
      <SelectContent>
        {tables.map((t) => (
          <SelectItem key={t.id} value={String(t.id)}>
            {t.label || t.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
