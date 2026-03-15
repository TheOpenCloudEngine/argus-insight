"use client"

import { forwardRef, useImperativeHandle, useState } from "react"
import { HelpCircle, Plus, Trash2 } from "lucide-react"
import { Button } from "@workspace/ui/components/button"
import { Checkbox } from "@workspace/ui/components/checkbox"
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"
import { RadioGroup, RadioGroupItem } from "@workspace/ui/components/radio-group"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"
import { Textarea } from "@workspace/ui/components/textarea"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@workspace/ui/components/tooltip"
import { cn } from "@workspace/ui/lib/utils"

export interface ConfigItem {
  name: string
  key: string
  type: "checkbox" | "inputtext" | "textfield" | "radio" | "textarea" | "key-value-description"
  dataType?: string
  multipleSelection?: boolean
  description?: string
  options?: string[]
  values?: string[]
  default?: string | number
  appendable?: boolean
  unit?: string[]
  defaultUnit?: string
  value?: string
  required?: boolean
}

interface KeyValueRow {
  key: string
  value: string
  description: string
}

export interface ConfigFieldHandle {
  getValue(): unknown
}

interface ConfigFieldProps {
  item: ConfigItem
}

function validateNumeric(val: string, dataType?: string): string | null {
  if (!val) return null
  if (dataType === "Integer") {
    return /^-?\d+$/.test(val) ? null : "정수를 입력해주세요."
  }
  if (dataType === "Double" || dataType === "Float") {
    return /^-?\d+(\.\d+)?$/.test(val) ? null : "숫자를 입력해주세요."
  }
  return null
}

export const ConfigField = forwardRef<ConfigFieldHandle, ConfigFieldProps>(({ item }, ref) => {
  const [checkedOptions, setCheckedOptions] = useState<string[]>(() => {
    if (item.type === "checkbox") {
      if (item.values) return item.values
      if (item.default) return [String(item.default)]
    }
    return []
  })

  const [inputValues, setInputValues] = useState<string[]>(() => {
    if (item.type === "inputtext") {
      if (item.values) return item.values
      if (item.default !== undefined) return [String(item.default)]
    }
    return [""]
  })
  const [inputErrors, setInputErrors] = useState<(string | null)[]>(() =>
    (item.type === "inputtext" ? (item.values ?? [""]) : [""]).map(() => null)
  )

  const [textValue, setTextValue] = useState("")
  const [textError, setTextError] = useState<string | null>(null)
  const [selectedUnit, setSelectedUnit] = useState(item.defaultUnit ?? item.unit?.[0] ?? "")

  const [radioValue, setRadioValue] = useState(
    item.type === "radio" ? (item.default ? String(item.default) : item.options?.[0] ?? "") : ""
  )

  const [textareaValue, setTextareaValue] = useState(item.value ?? "")

  const [kvRows, setKvRows] = useState<KeyValueRow[]>([{ key: "", value: "", description: "" }])

  useImperativeHandle(ref, () => ({
    getValue() {
      switch (item.type) {
        case "checkbox":      return checkedOptions
        case "inputtext":     return inputValues
        case "textfield":     return { value: textValue, unit: selectedUnit }
        case "radio":         return radioValue
        case "textarea":      return textareaValue
        case "key-value-description": return kvRows
        default:              return null
      }
    },
  }))

  const toggleCheckbox = (option: string) => {
    if (item.multipleSelection) {
      setCheckedOptions((prev) =>
        prev.includes(option) ? prev.filter((o) => o !== option) : [...prev, option]
      )
    } else {
      setCheckedOptions((prev) => (prev.includes(option) ? [] : [option]))
    }
  }

  const updateInputValue = (index: number, val: string) => {
    setInputValues((prev) => prev.map((v, i) => (i === index ? val : v)))
    setInputErrors((prev) =>
      prev.map((e, i) => (i === index ? validateNumeric(val, item.dataType) : e))
    )
  }

  const addInputValue = () => {
    setInputValues((prev) => [...prev, ""])
    setInputErrors((prev) => [...prev, null])
  }

  const removeInputValue = (index: number) => {
    setInputValues((prev) => prev.filter((_, i) => i !== index))
    setInputErrors((prev) => prev.filter((_, i) => i !== index))
  }

  const addKvRow = () => setKvRows((prev) => [...prev, { key: "", value: "", description: "" }])

  const removeKvRow = (index: number) => {
    setKvRows((prev) => prev.filter((_, i) => i !== index))
  }

  const updateKvRow = (index: number, field: keyof KeyValueRow, val: string) => {
    setKvRows((prev) =>
      prev.map((row, i) => (i === index ? { ...row, [field]: val } : row))
    )
  }

  return (
    <div className="grid grid-cols-[1fr_2fr_auto] gap-x-6 gap-y-1 py-4">
      {/* Col 1: name + key */}
      <div className="flex flex-col gap-1 pr-2">
        <span
          className={cn(
            "text-sm font-medium leading-snug",
            item.required && "text-destructive"
          )}
        >
          {item.name}
        </span>
        <span className="text-xs text-muted-foreground font-mono opacity-60">{item.key}</span>
      </div>

      {/* Col 2: input control */}
      <div className="flex flex-col gap-2">
        {/* checkbox */}
        {item.type === "checkbox" && (
          <div className="flex flex-col gap-2">
            {(item.options ?? item.values ?? []).map((option) => (
              <div key={option} className="flex items-center gap-2">
                <Checkbox
                  id={`${item.key}-${option}`}
                  checked={checkedOptions.includes(option)}
                  onCheckedChange={() => toggleCheckbox(option)}
                />
                <Label htmlFor={`${item.key}-${option}`} className="text-sm font-normal cursor-pointer">
                  {option}
                </Label>
              </div>
            ))}
          </div>
        )}

        {/* inputtext */}
        {item.type === "inputtext" && (
          <div className="flex flex-col gap-2">
            {inputValues.map((val, idx) => (
              <div key={idx} className="flex flex-col gap-1">
                <div className="flex items-center gap-2">
                  <Input
                    value={val}
                    onChange={(e) => updateInputValue(idx, e.target.value)}
                    className={cn("h-8 text-sm", inputErrors[idx] && "border-destructive")}
                    placeholder={item.default !== undefined ? String(item.default) : ""}
                  />
                  {item.appendable && inputValues.length > 1 && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 shrink-0 text-muted-foreground hover:text-destructive"
                      onClick={() => removeInputValue(idx)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  )}
                </div>
                {inputErrors[idx] && (
                  <span className="text-xs text-destructive">{inputErrors[idx]}</span>
                )}
              </div>
            ))}
            {item.appendable && (
              <div className="flex justify-end">
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-1.5 text-xs h-7"
                  onClick={addInputValue}
                >
                  <Plus className="h-3 w-3" />
                  항목 추가
                </Button>
              </div>
            )}
          </div>
        )}

        {/* textfield with unit */}
        {item.type === "textfield" && (
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2">
              <Input
                value={textValue}
                onChange={(e) => {
                  setTextValue(e.target.value)
                  setTextError(validateNumeric(e.target.value, item.dataType))
                }}
                className={cn("h-8 text-sm w-40", textError && "border-destructive")}
                placeholder="0"
              />
              {item.unit && item.unit.length > 0 && (
                <Select value={selectedUnit} onValueChange={setSelectedUnit}>
                  <SelectTrigger className="h-8 w-24 text-sm">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {item.unit.map((u) => (
                      <SelectItem key={u} value={u} className="text-sm">{u}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>
            {textError && <span className="text-xs text-destructive">{textError}</span>}
          </div>
        )}

        {/* radio */}
        {item.type === "radio" && (
          <RadioGroup value={radioValue} onValueChange={setRadioValue} className="flex flex-col gap-2">
            {(item.options ?? []).map((option) => (
              <div key={option} className="flex items-center gap-2">
                <RadioGroupItem id={`${item.key}-${option}`} value={option} />
                <Label
                  htmlFor={`${item.key}-${option}`}
                  className={cn("text-sm font-normal cursor-pointer", radioValue === option && "font-medium")}
                >
                  {option}
                </Label>
              </div>
            ))}
          </RadioGroup>
        )}

        {/* textarea */}
        {item.type === "textarea" && (
          <Textarea
            value={textareaValue}
            onChange={(e) => setTextareaValue(e.target.value)}
            className="text-sm font-mono min-h-[100px] resize-y"
          />
        )}

        {/* key-value-description: vertical per row */}
        {item.type === "key-value-description" && (
          <div className="flex flex-col gap-3">
            {kvRows.map((row, idx) => (
              <div key={idx} className="flex flex-col gap-1.5 rounded-md border bg-muted/30 p-3">
                {(["key", "value", "description"] as const).map((field) => (
                  <div key={field} className="grid grid-cols-[6rem_1fr] items-center gap-2">
                    <span className="text-xs text-muted-foreground font-medium capitalize text-right">
                      {field === "key" ? "Name" : field.charAt(0).toUpperCase() + field.slice(1)}
                    </span>
                    <Input
                      value={row[field]}
                      onChange={(e) => updateKvRow(idx, field, e.target.value)}
                      className="h-8 text-sm"
                    />
                  </div>
                ))}
                {item.appendable && kvRows.length > 1 && (
                  <div className="flex justify-end pt-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 text-muted-foreground hover:text-destructive"
                      onClick={() => removeKvRow(idx)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                )}
              </div>
            ))}
            {item.appendable && (
              <div className="flex justify-end">
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-1.5 text-xs h-7"
                  onClick={addKvRow}
                >
                  <Plus className="h-3 w-3" />
                  항목 추가
                </Button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Col 3: help icon */}
      <div className="flex items-start pt-0.5">
        {item.description ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <HelpCircle className="h-4 w-4 text-muted-foreground cursor-help shrink-0" />
            </TooltipTrigger>
            <TooltipContent side="left" className="max-w-72">
              <p className="text-xs leading-relaxed">{item.description}</p>
            </TooltipContent>
          </Tooltip>
        ) : (
          <span className="w-4" />
        )}
      </div>
    </div>
  )
})

ConfigField.displayName = "ConfigField"
