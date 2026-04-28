import { useState, useEffect, useRef, useCallback } from "react"
import { Input } from "@/components/ui/input"
import { X } from "lucide-react"

interface Option {
  id: number
  label: string
}

interface Props {
  value: number | null
  onChange: (id: number | null) => void
  fetchOptions: (q: string) => Promise<Option[]>
  placeholder?: string
  disabled?: boolean
  className?: string
}

export default function SearchSelect({
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
  const [selectedLabel, setSelectedLabel] = useState("")
  const containerRef = useRef<HTMLDivElement>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout>>()

  // Load initial label if value is set
  useEffect(() => {
    if (value != null && value > 0 && !selectedLabel) {
      fetchOptions("").then((opts) => {
        const match = opts.find((o) => o.id === value)
        if (match) setSelectedLabel(match.label)
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

  const handleSelect = (opt: Option) => {
    onChange(opt.id)
    setSelectedLabel(opt.label)
    setQuery("")
    setOpen(false)
  }

  const handleClear = (e: React.MouseEvent) => {
    e.stopPropagation()
    onChange(null)
    setSelectedLabel("")
    setQuery("")
  }

  return (
    <div ref={containerRef} className={`relative ${className}`}>
      <div
        className="flex items-center border rounded-md px-3 py-2 text-sm cursor-pointer bg-background hover:border-ring"
        onClick={() => { if (!disabled) setOpen(!open) }}
      >
        <span className={`flex-1 truncate ${!selectedLabel ? "text-muted-foreground" : ""}`}>
          {selectedLabel || placeholder}
        </span>
        {selectedLabel && !disabled && (
          <button
            className="ml-1 text-muted-foreground hover:text-foreground"
            onClick={handleClear}
          >
            <X className="h-3 w-3" />
          </button>
        )}
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
                className={`px-3 py-2 text-sm cursor-pointer hover:bg-accent ${opt.id === value ? "bg-accent" : ""}`}
                onClick={() => handleSelect(opt)}
              >
                {opt.label}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
