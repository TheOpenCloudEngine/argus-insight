"use client"

import { useCallback } from "react"
import { HelpCircle } from "lucide-react"
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"
import { Checkbox } from "@workspace/ui/components/checkbox"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@workspace/ui/components/tooltip"
import type { JsonSchema, JsonSchemaProperty } from "@/features/software-deployment/types"

interface DynamicConfigFormProps {
  schema: JsonSchema
  values: Record<string, unknown>
  onChange: (values: Record<string, unknown>) => void
}

function prettifyKey(key: string): string {
  return key
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/[_-]/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

export function DynamicConfigForm({ schema, values, onChange }: DynamicConfigFormProps) {
  const handleChange = useCallback(
    (key: string, value: unknown) => {
      onChange({ ...values, [key]: value })
    },
    [values, onChange],
  )

  if (!schema.properties || Object.keys(schema.properties).length === 0) {
    return <div />
  }

  const requiredFields = new Set(schema.required ?? [])

  return (
    <div className="rounded-md border divide-y">
      {Object.entries(schema.properties).map(([key, property]) => (
        <FieldRow
          key={key}
          fieldKey={key}
          property={property}
          value={values[key]}
          required={requiredFields.has(key)}
          onChange={handleChange}
        />
      ))}
    </div>
  )
}

interface FieldRowProps {
  fieldKey: string
  property: JsonSchemaProperty
  value: unknown
  required: boolean
  onChange: (key: string, value: unknown) => void
}

function FieldRow({ fieldKey, property, value, required, onChange }: FieldRowProps) {
  const label = property.title || prettifyKey(fieldKey)
  const description = property.description

  return (
    <div className="grid grid-cols-[200px_1fr_32px] items-start gap-3 px-4 py-3">
      {/* Label + Key */}
      <div className="flex flex-col gap-0.5 pt-1.5">
        <Label className="text-sm font-medium leading-tight">
          {label}
          {required && <span className="text-destructive ml-0.5">*</span>}
        </Label>
        <span className="text-xs text-muted-foreground font-mono">{fieldKey}</span>
      </div>

      {/* Input control */}
      <div>
        <FieldInput
          fieldKey={fieldKey}
          property={property}
          value={value}
          onChange={onChange}
        />
      </div>

      {/* Help icon */}
      <div className="pt-1.5">
        {description ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <HelpCircle className="h-4 w-4 text-muted-foreground cursor-help" />
            </TooltipTrigger>
            <TooltipContent side="left" className="max-w-xs text-xs">
              {description}
            </TooltipContent>
          </Tooltip>
        ) : (
          <div className="h-4 w-4" />
        )}
      </div>
    </div>
  )
}

interface FieldInputProps {
  fieldKey: string
  property: JsonSchemaProperty
  value: unknown
  onChange: (key: string, value: unknown) => void
}

function FieldInput({ fieldKey, property, value, onChange }: FieldInputProps) {
  // string with enum -> Select dropdown
  if (property.type === "string" && property.enum) {
    return (
      <Select
        value={(value as string) ?? ""}
        onValueChange={(v) => onChange(fieldKey, v)}
      >
        <SelectTrigger className="h-9">
          <SelectValue
            placeholder={
              property.default != null ? String(property.default) : `Select...`
            }
          />
        </SelectTrigger>
        <SelectContent>
          {property.enum.map((option) => (
            <SelectItem key={String(option)} value={String(option)}>
              {String(option)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    )
  }

  // string without enum -> text input
  if (property.type === "string") {
    return (
      <Input
        className="h-9"
        type="text"
        value={(value as string) ?? ""}
        placeholder={property.default != null ? String(property.default) : undefined}
        onChange={(e) => onChange(fieldKey, e.target.value)}
      />
    )
  }

  // integer or number -> number input
  if (property.type === "integer" || property.type === "number") {
    return (
      <Input
        className="h-9"
        type="number"
        value={value != null ? String(value) : ""}
        placeholder={property.default != null ? String(property.default) : undefined}
        min={property.minimum}
        max={property.maximum}
        step={property.type === "integer" ? 1 : "any"}
        onChange={(e) => {
          const raw = e.target.value
          if (raw === "") {
            onChange(fieldKey, undefined)
            return
          }
          const parsed =
            property.type === "integer" ? parseInt(raw, 10) : parseFloat(raw)
          if (!isNaN(parsed)) {
            onChange(fieldKey, parsed)
          }
        }}
      />
    )
  }

  // boolean -> checkbox
  if (property.type === "boolean") {
    return (
      <div className="flex items-center h-9">
        <Checkbox
          id={fieldKey}
          checked={(value as boolean) ?? (property.default as boolean) ?? false}
          onCheckedChange={(checked) => onChange(fieldKey, Boolean(checked))}
        />
      </div>
    )
  }

  // array of strings -> comma-separated input
  if (property.type === "array" && property.items?.type === "string") {
    const arrayValue = Array.isArray(value) ? (value as string[]).join(", ") : ""
    return (
      <Input
        className="h-9"
        type="text"
        value={arrayValue}
        placeholder={
          property.default != null
            ? (property.default as string[]).join(", ")
            : "Comma-separated values"
        }
        onChange={(e) => {
          const raw = e.target.value
          if (raw.trim() === "") {
            onChange(fieldKey, [])
            return
          }
          const items = raw.split(",").map((s) => s.trim())
          onChange(fieldKey, items)
        }}
      />
    )
  }

  // Unsupported type fallback
  return (
    <Input
      className="h-9"
      type="text"
      value={value != null ? String(value) : ""}
      placeholder={property.default != null ? String(property.default) : undefined}
      onChange={(e) => onChange(fieldKey, e.target.value)}
    />
  )
}
