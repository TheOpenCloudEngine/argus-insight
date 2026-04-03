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

export interface ColumnDef {
  name: string
  dtype: string
  action: string   // feature | target | exclude
}

const TYPES = ["integer", "float", "string", "boolean", "datetime", "category"]
const ACTIONS = [
  { value: "feature", label: "Feature", color: "" },
  { value: "target", label: "Target", color: "text-blue-600" },
  { value: "exclude", label: "Exclude", color: "text-red-500 italic" },
]

interface ColumnsEditorProps {
  columns: ColumnDef[]
  onChange: (columns: ColumnDef[]) => void
  typeEditable?: boolean  // false for Parquet (types from schema)
  rowCount?: number
}

export function ColumnsEditor({ columns, onChange, typeEditable = true, rowCount }: ColumnsEditorProps) {
  const updateColumn = (idx: number, field: keyof ColumnDef, value: string) => {
    const updated = columns.map((c, i) => {
      if (i !== idx) {
        // If setting target, clear other targets
        if (field === "action" && value === "target") {
          return c.action === "target" ? { ...c, action: "feature" } : c
        }
        return c
      }
      return { ...c, [field]: value }
    })
    onChange(updated)
  }

  if (columns.length === 0) return null

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <Label className="text-sm font-medium">Columns</Label>
        {rowCount != null && (
          <span className="text-sm text-muted-foreground">
            {columns.length} columns{rowCount > 0 ? ` · ${rowCount.toLocaleString()} rows` : ""}
          </span>
        )}
      </div>
      <div className="max-h-[325px] overflow-y-auto rounded border text-sm">
        <table className="w-full">
          <thead className="sticky top-0 bg-muted/80 text-sm">
            <tr>
              <th className="px-2 py-1 text-left font-medium w-[40%]">Column</th>
              <th className="px-2 py-1 text-left font-medium w-[30%]">Type</th>
              <th className="px-2 py-1 text-left font-medium w-[30%]">Action</th>
            </tr>
          </thead>
          <tbody>
            {columns.map((col, i) => (
              <tr key={col.name} className="border-t hover:bg-muted/30">
                <td className="px-2 py-1 font-mono text-sm">{col.name}</td>
                <td className="px-2 py-1">
                  {typeEditable ? (
                    <Select value={col.dtype} onValueChange={(v) => updateColumn(i, "dtype", v)}>
                      <SelectTrigger className="h-6 text-sm px-1.5"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {TYPES.map((t) => (
                          <SelectItem key={t} value={t} className="text-sm">{t}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : (
                    <span className="text-sm text-muted-foreground">{col.dtype}</span>
                  )}
                </td>
                <td className="px-2 py-1">
                  <Select value={col.action} onValueChange={(v) => updateColumn(i, "action", v)}>
                    <SelectTrigger className={`h-6 text-sm px-1.5 ${ACTIONS.find((a) => a.value === col.action)?.color || ""}`}>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {ACTIONS.map((a) => (
                        <SelectItem key={a.value} value={a.value} className={`text-sm ${a.color}`}>{a.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
