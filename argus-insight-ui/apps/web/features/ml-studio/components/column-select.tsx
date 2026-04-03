"use client"

import { Checkbox } from "@workspace/ui/components/checkbox"
import { Label } from "@workspace/ui/components/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"

export interface ColumnInfo {
  name: string
  dtype: string
}

// ── Single column select (dropdown) ───────────────────────

interface SingleColumnSelectProps {
  label?: string
  value: string
  onChange: (value: string) => void
  columns: ColumnInfo[]
  filterType?: string[]   // e.g., ["integer", "float"] to show only numeric
  placeholder?: string
}

export function SingleColumnSelect({
  label,
  value,
  onChange,
  columns,
  filterType,
  placeholder = "Select column",
}: SingleColumnSelectProps) {
  const filtered = filterType
    ? columns.filter((c) => filterType.includes(c.dtype))
    : columns

  return (
    <div className="space-y-1">
      {label && <Label className="text-sm">{label}</Label>}
      <Select value={value || "_none_"} onValueChange={(v) => onChange(v === "_none_" ? "" : v)}>
        <SelectTrigger className="h-7 text-sm">
          <SelectValue placeholder={placeholder} />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="_none_" className="text-sm text-muted-foreground">{placeholder}</SelectItem>
          {filtered.map((c) => (
            <SelectItem key={c.name} value={c.name} className="text-sm">
              {c.name} <span className="text-muted-foreground ml-1">({c.dtype})</span>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {filtered.length === 0 && columns.length > 0 && (
        <p className="text-[11px] text-muted-foreground">No matching columns{filterType ? ` (need: ${filterType.join(", ")})` : ""}</p>
      )}
      {columns.length === 0 && (
        <p className="text-[11px] text-amber-500">Connect a Source node to see columns</p>
      )}
    </div>
  )
}

// ── Multi column select (checkboxes) ──────────────────────

interface MultiColumnSelectProps {
  label?: string
  selected: string[]
  onChange: (selected: string[]) => void
  columns: ColumnInfo[]
  filterType?: string[]
  maxHeight?: string
}

export function MultiColumnSelect({
  label,
  selected,
  onChange,
  columns,
  filterType,
  maxHeight = "150px",
}: MultiColumnSelectProps) {
  const filtered = filterType
    ? columns.filter((c) => filterType.includes(c.dtype))
    : columns

  const toggle = (name: string) => {
    if (selected.includes(name)) {
      onChange(selected.filter((s) => s !== name))
    } else {
      onChange([...selected, name])
    }
  }

  const selectAll = () => onChange(filtered.map((c) => c.name))
  const deselectAll = () => onChange([])

  return (
    <div className="space-y-1">
      {label && (
        <div className="flex items-center justify-between">
          <Label className="text-sm">{label}</Label>
          <div className="flex gap-2 text-[11px]">
            <button type="button" className="text-primary hover:underline" onClick={selectAll}>All</button>
            <button type="button" className="text-muted-foreground hover:underline" onClick={deselectAll}>None</button>
          </div>
        </div>
      )}
      {columns.length === 0 ? (
        <p className="text-[11px] text-amber-500">Connect a Source node to see columns</p>
      ) : (
        <div className="overflow-y-auto rounded border p-1.5 space-y-0.5" style={{ maxHeight }}>
          {filtered.map((c) => (
            <label key={c.name} className="flex items-center gap-2 px-1 py-0.5 rounded hover:bg-muted/50 cursor-pointer text-sm">
              <Checkbox checked={selected.includes(c.name)} onCheckedChange={() => toggle(c.name)} />
              <span className="font-mono text-sm">{c.name}</span>
              <span className="text-muted-foreground text-sm ml-auto">{c.dtype}</span>
            </label>
          ))}
          {filtered.length === 0 && (
            <p className="text-[11px] text-muted-foreground px-1">No matching columns</p>
          )}
        </div>
      )}
      {selected.length > 0 && (
        <p className="text-[11px] text-muted-foreground">{selected.length} selected</p>
      )}
    </div>
  )
}
