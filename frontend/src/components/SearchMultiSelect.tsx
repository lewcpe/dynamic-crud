import { useState, useEffect, useRef } from "react"
import { Input } from "@/components/ui/input"
import { X } from "lucide-react"

interface Option {
  id: number
  label: string
}

interface Props {
  value: number[]
  onChange: (ids: number[]) => void
  fetchOptions: (q: string) => Promise<Option[]>
  placeholder?: string
  disabled?: boolean
  className?: string
}

export default function SearchMultiSelect({
  value,
  onChange,
  fetchOptions,
  placeholder = "Search...",
  disabled = false,
  className = "",
}: Props) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState("")
  const [options, setOptions] = useState<Option[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedLabels, setSelectedLabels] = useState<Map<number, string>>(new Map())
  const containerRef = useRef<HTMLDivElement>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout>>()

  // Load labels for selected values
  useEffect(() => {
    if (value.length > 0 && value.some((v) => !selectedLabels.has(v))) {
      fetchOptions("").then((opts) => {
        const map = new Map(selectedLabels)
        opts.forEach((o) => {
          if (value.includes(o.id)) map.set(o.id, o.label)
        })
        setSelectedLabels(map)
      })
    }
  }, [value])

  // Search with debounce
  useEffect(() => {
    if (!open) return
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(async () => {
      setLoading(true)
      try {
        const results = await fetchOptions(query)
        setOptions(results)
        // Update labels
        const map = new Map(selectedLabels)
        results.forEach((o) => map.set(o.id, o.label))
        setSelectedLabels(map)
      } catch {
        setOptions([])
      }
      setLoading(false)
    }, 200)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [query, open, fetchOptions])

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [])

  const handleToggle = (opt: Option) => {
    const next = value.includes(opt.id)
      ? value.filter((v) => v !== opt.id)
      : [...value, opt.id]
    onChange(next)
  }

  const handleRemove = (id: number) => {
    onChange(value.filter((v) => v !== id))
  }

  const getLabel = (id: number) => selectedLabels.get(id) || `#${id}`

  return (
    <div ref={containerRef} className={`relative ${className}`}>
      {/* Selected tags */}
      {value.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-1">
          {value.map((id) => (
            <span
              key={id}
              className="inline-flex items-center gap-1 px-2 py-0.5 text-xs bg-secondary rounded"
            >
              {getLabel(id)}
              {!disabled && (
                <button
                  className="text-muted-foreground hover:text-foreground"
                  onClick={() => handleRemove(id)}
                >
                  <X className="h-3 w-3" />
                </button>
              )}
            </span>
          ))}
        </div>
      )}
      <div
        className="flex items-center border rounded-md px-3 py-2 text-sm cursor-pointer bg-background hover:border-ring"
        onClick={() => { if (!disabled) setOpen(!open) }}
      >
        <span className="flex-1 text-muted-foreground">
          {value.length === 0 ? placeholder : `${value.length} selected`}
        </span>
      </div>
      {open && (
        <div className="absolute z-50 w-full mt-1 bg-background border rounded-md shadow-lg">
          <div className="p-2">
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Type to search..."
              className="h-8 text-sm"
              autoFocus
            />
          </div>
          <div className="max-h-48 overflow-y-auto">
            {loading && (
              <div className="px-3 py-2 text-xs text-muted-foreground">Loading...</div>
            )}
            {!loading && options.length === 0 && (
              <div className="px-3 py-2 text-xs text-muted-foreground">
                {query ? "No results" : "No options"}
              </div>
            )}
            {!loading && options.map((opt) => (
              <div
                key={opt.id}
                className={`px-3 py-2 text-sm cursor-pointer hover:bg-accent flex items-center gap-2 ${value.includes(opt.id) ? "bg-accent" : ""}`}
                onClick={() => handleToggle(opt)}
              >
                <input
                  type="checkbox"
                  checked={value.includes(opt.id)}
                  readOnly
                />
                {opt.label}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
