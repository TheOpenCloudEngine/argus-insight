"use client"

import { Plus, Trash2 } from "lucide-react"
import { Button } from "@workspace/ui/components/button"
import { Checkbox } from "@workspace/ui/components/checkbox"
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"

import { SingleColumnSelect, MultiColumnSelect, type ColumnInfo } from "./column-select"

interface TransformConfigProps {
  config: Record<string, any>
  onChange: (key: string, value: any) => void
  columns?: ColumnInfo[]
}

// ── Fill Null ─────────────────────────────────────────────

export function FillNullConfig({
  config,
  onChange,
  columns,
}: TransformConfigProps) {
  return (
    <div className="space-y-3">
      <div className="space-y-1">
        <Label className="text-sm">Strategy</Label>
        <Select value={config.strategy || "median"} onValueChange={(v) => onChange("strategy", v)}>
          <SelectTrigger className="h-8 text-sm"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="mean" className="text-sm">Mean — average (numeric columns)</SelectItem>
            <SelectItem value="median" className="text-sm">Median — middle value (robust to outliers)</SelectItem>
            <SelectItem value="mode" className="text-sm">Mode — most frequent (categorical)</SelectItem>
            <SelectItem value="constant" className="text-sm">Constant — fill with a fixed value</SelectItem>
            <SelectItem value="drop" className="text-sm">Drop — remove rows with missing values</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {config.strategy === "constant" && (
        <div className="space-y-1">
          <Label className="text-sm">Fill Value</Label>
          <Input
            value={config.constant_value ?? "0"}
            onChange={(e) => onChange("constant_value", e.target.value)}
            placeholder="0"
            className="h-8 text-sm"
          />
          <p className="text-[11px] text-muted-foreground">Value to fill missing cells with</p>
        </div>
      )}

      <div className="space-y-1">
        <Label className="text-sm">Apply to</Label>
        <Select value={config.apply_to || "all"} onValueChange={(v) => onChange("apply_to", v)}>
          <SelectTrigger className="h-8 text-sm"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all" className="text-sm">All columns with missing values</SelectItem>
            <SelectItem value="numeric" className="text-sm">Numeric columns only</SelectItem>
            <SelectItem value="categorical" className="text-sm">Categorical columns only</SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>
  )
}

// ── Encode ─────────────────────────────────────────────────

export function EncodeConfig({
  config,
  onChange,
  columns,
}: TransformConfigProps) {
  return (
    <div className="space-y-3">
      <div className="space-y-1">
        <Label className="text-sm">Method</Label>
        <Select value={config.method || "label"} onValueChange={(v) => onChange("method", v)}>
          <SelectTrigger className="h-8 text-sm"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="label" className="text-sm">Label — assign 0,1,2... (tree models)</SelectItem>
            <SelectItem value="onehot" className="text-sm">One-Hot — binary columns (linear models)</SelectItem>
            <SelectItem value="ordinal" className="text-sm">Ordinal — preserve order (low→high)</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {config.method === "onehot" && (
        <div className="flex items-center gap-2">
          <Checkbox
            checked={config.drop_first ?? false}
            onCheckedChange={(v) => onChange("drop_first", !!v)}
          />
          <Label className="text-sm">Drop first column (avoid multicollinearity)</Label>
        </div>
      )}

      {config.method === "ordinal" && (
        <div className="space-y-1">
          <Label className="text-sm">Value Order (comma-separated)</Label>
          <Input
            value={config.ordinal_order ?? ""}
            onChange={(e) => onChange("ordinal_order", e.target.value)}
            placeholder="low, medium, high"
            className="h-8 text-sm"
          />
          <p className="text-[11px] text-muted-foreground">Define category order from lowest to highest</p>
        </div>
      )}

      <div className="space-y-1">
        <Label className="text-sm">Apply to</Label>
        <Select value={config.apply_to || "all"} onValueChange={(v) => onChange("apply_to", v)}>
          <SelectTrigger className="h-8 text-sm"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all" className="text-sm">All string/category columns</SelectItem>
            <SelectItem value="string" className="text-sm">String columns only</SelectItem>
            <SelectItem value="category" className="text-sm">Category columns only</SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>
  )
}

// ── Scale ──────────────────────────────────────────────────

export function ScaleConfig({
  config,
  onChange,
  columns,
}: TransformConfigProps) {
  return (
    <div className="space-y-3">
      <div className="space-y-1">
        <Label className="text-sm">Method</Label>
        <Select value={config.method || "standard"} onValueChange={(v) => onChange("method", v)}>
          <SelectTrigger className="h-8 text-sm"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="standard" className="text-sm">Standard — mean=0, std=1 (most common)</SelectItem>
            <SelectItem value="minmax" className="text-sm">MinMax — scale to custom range</SelectItem>
            <SelectItem value="robust" className="text-sm">Robust — median/IQR (outlier resistant)</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {config.method === "minmax" && (
        <div className="grid grid-cols-2 gap-2">
          <div className="space-y-1">
            <Label className="text-sm">Min</Label>
            <Input
              type="number"
              value={config.range_min ?? 0}
              onChange={(e) => onChange("range_min", parseFloat(e.target.value) || 0)}
              className="h-8 text-sm"
            />
          </div>
          <div className="space-y-1">
            <Label className="text-sm">Max</Label>
            <Input
              type="number"
              value={config.range_max ?? 1}
              onChange={(e) => onChange("range_max", parseFloat(e.target.value) || 1)}
              className="h-8 text-sm"
            />
          </div>
        </div>
      )}

      <div className="space-y-1">
        <Label className="text-sm">Apply to</Label>
        <Select value={config.apply_to || "all"} onValueChange={(v) => onChange("apply_to", v)}>
          <SelectTrigger className="h-8 text-sm"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all" className="text-sm">All numeric columns</SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>
  )
}

// ── Split ──────────────────────────────────────────────────

export function SplitConfig({
  config,
  onChange,
  columns,
}: TransformConfigProps) {
  const testSize = config.test_size ?? 0.2
  const trainPct = Math.round((1 - testSize) * 100)
  const testPct = Math.round(testSize * 100)

  return (
    <div className="space-y-3">
      <SingleColumnSelect
        label="Target Column"
        value={config.target_column ?? ""}
        onChange={(v) => onChange("target_column", v)}
        columns={columns || []}
        placeholder="Select target column (y)"
      />

      <div className="space-y-1">
        <div className="flex items-center justify-between">
          <Label className="text-sm">Test Size</Label>
          <span className="text-sm font-mono text-muted-foreground">{testPct}%</span>
        </div>
        <input
          type="range"
          min="0.05"
          max="0.5"
          step="0.05"
          value={testSize}
          onChange={(e) => onChange("test_size", parseFloat(e.target.value))}
          className="w-full accent-primary"
        />
        <div className="flex justify-between text-[11px] text-muted-foreground">
          <span>Train {trainPct}%</span>
          <span>Test {testPct}%</span>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <Checkbox
          checked={config.stratify ?? true}
          onCheckedChange={(v) => onChange("stratify", !!v)}
        />
        <div>
          <Label className="text-sm">Stratify</Label>
          <p className="text-[11px] text-muted-foreground">Maintain class ratio (for classification)</p>
        </div>
      </div>

      <div className="space-y-1">
        <Label className="text-sm">Random Seed</Label>
        <Input
          type="number"
          value={config.random_seed ?? 42}
          onChange={(e) => onChange("random_seed", parseInt(e.target.value) || 42)}
          className="h-8 text-sm"
        />
        <p className="text-[11px] text-muted-foreground">Fixed seed for reproducible splits</p>
      </div>
    </div>
  )
}

// ── Filter Rows ───────────────────────────────────────────

interface FilterCondition {
  column: string
  operator: string
  value: string
}

const OPERATORS = [
  { value: ">", label: "> greater than" },
  { value: ">=", label: ">= greater or equal" },
  { value: "<", label: "< less than" },
  { value: "<=", label: "<= less or equal" },
  { value: "==", label: "== equals" },
  { value: "!=", label: "!= not equals" },
  { value: "contains", label: "contains" },
  { value: "not_null", label: "is not null" },
]

export function FilterConfig({
  config,
  onChange,
  columns,
}: TransformConfigProps) {
  const conditions: FilterCondition[] = config.conditions || [{ column: "", operator: ">", value: "" }]
  const logic = config.logic || "AND"

  const updateCondition = (idx: number, field: string, val: string) => {
    const updated = conditions.map((c, i) => (i === idx ? { ...c, [field]: val } : c))
    onChange("conditions", updated)
  }

  const addCondition = () => {
    onChange("conditions", [...conditions, { column: "", operator: ">", value: "" }])
  }

  const removeCondition = (idx: number) => {
    if (conditions.length <= 1) return
    onChange("conditions", conditions.filter((_, i) => i !== idx))
  }

  return (
    <div className="space-y-3">
      <div className="space-y-1">
        <Label className="text-sm">Logic</Label>
        <Select value={logic} onValueChange={(v) => onChange("logic", v)}>
          <SelectTrigger className="h-8 text-sm"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="AND" className="text-sm">AND — all conditions must match</SelectItem>
            <SelectItem value="OR" className="text-sm">OR — any condition matches</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {conditions.map((cond, i) => (
        <div key={i} className="space-y-1.5 rounded border p-2 bg-muted/20">
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-muted-foreground">Condition {i + 1}</span>
            {conditions.length > 1 && (
              <Button variant="ghost" size="icon" className="h-5 w-5" onClick={() => removeCondition(i)}>
                <Trash2 className="h-3 w-3 text-destructive" />
              </Button>
            )}
          </div>
          <SingleColumnSelect
            value={cond.column}
            onChange={(v) => updateCondition(i, "column", v)}
            columns={columns || []}
            placeholder="Select column"
          />
          <Select value={cond.operator} onValueChange={(v) => updateCondition(i, "operator", v)}>
            <SelectTrigger className="h-7 text-sm"><SelectValue /></SelectTrigger>
            <SelectContent>
              {OPERATORS.map((op) => (
                <SelectItem key={op.value} value={op.value} className="text-sm">{op.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          {cond.operator !== "not_null" && (
            <Input
              placeholder="Value"
              value={cond.value}
              onChange={(e) => updateCondition(i, "value", e.target.value)}
              className="h-7 text-sm"
            />
          )}
        </div>
      ))}

      <Button variant="outline" size="sm" className="w-full text-sm" onClick={addCondition}>
        <Plus className="mr-1.5 h-3 w-3" /> Add Condition
      </Button>
    </div>
  )
}

// ── Feature Engineering ───────────────────────────────────

interface FeatureExpr {
  name: string
  expression: string
}

const FUNCTION_HINTS = [
  "price * quantity",
  "np.log(salary + 1)",
  "age // 10 * 10",
  "np.sqrt(area)",
  "col1 / col2",
  "col.str.len()",
]

export function FeatureEngConfig({
  config,
  onChange,
  columns,
}: TransformConfigProps) {
  const features: FeatureExpr[] = config.features || [{ name: "", expression: "" }]

  const updateFeature = (idx: number, field: string, val: string) => {
    const updated = features.map((f, i) => (i === idx ? { ...f, [field]: val } : f))
    onChange("features", updated)
  }

  const addFeature = () => {
    onChange("features", [...features, { name: "", expression: "" }])
  }

  const removeFeature = (idx: number) => {
    if (features.length <= 1) return
    onChange("features", features.filter((_, i) => i !== idx))
  }

  return (
    <div className="space-y-3">
      {features.map((feat, i) => (
        <div key={i} className="space-y-1.5 rounded border p-2 bg-muted/20">
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-muted-foreground">Feature {i + 1}</span>
            {features.length > 1 && (
              <Button variant="ghost" size="icon" className="h-5 w-5" onClick={() => removeFeature(i)}>
                <Trash2 className="h-3 w-3 text-destructive" />
              </Button>
            )}
          </div>
          <Input
            placeholder="New column name (e.g., total_price)"
            value={feat.name}
            onChange={(e) => updateFeature(i, "name", e.target.value)}
            className="h-7 text-sm"
          />
          <Input
            placeholder="Expression (e.g., price * quantity)"
            value={feat.expression}
            onChange={(e) => updateFeature(i, "expression", e.target.value)}
            className="h-7 text-sm font-mono"
          />
        </div>
      ))}

      <Button variant="outline" size="sm" className="w-full text-sm" onClick={addFeature}>
        <Plus className="mr-1.5 h-3 w-3" /> Add Feature
      </Button>

      <div className="rounded bg-muted/30 p-2">
        <p className="text-[11px] text-muted-foreground font-medium mb-1">Expression examples:</p>
        <div className="flex flex-wrap gap-1">
          {FUNCTION_HINTS.map((h) => (
            <code key={h} className="bg-muted px-1 py-0.5 rounded text-[10px] font-mono">{h}</code>
          ))}
        </div>
      </div>

      {(columns || []).length > 0 && (
        <div className="rounded bg-muted/30 p-2">
          <p className="text-[11px] text-muted-foreground font-medium mb-1">Available columns:</p>
          <div className="flex flex-wrap gap-1">
            {columns!.map((c) => (
              <code key={c.name} className="bg-muted px-1 py-0.5 rounded text-[10px] font-mono">{c.name}</code>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Drop Columns ──────────────────────────────────────────

export function DropColumnsConfig({
  config,
  onChange,
  columns,
}: TransformConfigProps) {
  // Store as comma-separated string internally for compatibility
  const selected = (config.columns ?? "").split(",").map((s: string) => s.trim()).filter(Boolean)

  return (
    <div className="space-y-3">
      <MultiColumnSelect
        label="Columns to drop"
        selected={selected}
        onChange={(sel) => onChange("columns", sel.join(", "))}
        columns={columns || []}
        maxHeight="200px"
      />
      <p className="text-[11px] text-muted-foreground">Select columns that should not be used for training</p>
    </div>
  )
}

// ── Drop Duplicates ───────────────────────────────────────

export function DropDuplicatesConfig({
  config,
  onChange,
  columns,
}: TransformConfigProps) {
  const selected = (config.subset ?? "").split(",").map((s: string) => s.trim()).filter(Boolean)

  return (
    <div className="space-y-3">
      <MultiColumnSelect
        label="Subset columns (optional)"
        selected={selected}
        onChange={(sel) => onChange("subset", sel.join(", "))}
        columns={columns || []}
        maxHeight="150px"
      />
      <p className="text-[11px] text-muted-foreground">Check duplicates based on these columns only. Leave empty for all.</p>
      <div className="space-y-1">
        <Label className="text-sm">Keep</Label>
        <Select value={config.keep || "first"} onValueChange={(v) => onChange("keep", v)}>
          <SelectTrigger className="h-8 text-sm"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="first" className="text-sm">First occurrence</SelectItem>
            <SelectItem value="last" className="text-sm">Last occurrence</SelectItem>
            <SelectItem value="none" className="text-sm">Drop all duplicates</SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>
  )
}

// ── Type Cast ─────────────────────────────────────────────

export function TypeCastConfig({
  config,
  onChange,
  columns,
}: TransformConfigProps) {
  const casts: { column: string; to_type: string }[] = config.casts || [{ column: "", to_type: "int" }]

  const updateCast = (idx: number, field: string, val: string) => {
    const updated = casts.map((c, i) => (i === idx ? { ...c, [field]: val } : c))
    onChange("casts", updated)
  }
  const addCast = () => onChange("casts", [...casts, { column: "", to_type: "int" }])
  const removeCast = (idx: number) => {
    if (casts.length <= 1) return
    onChange("casts", casts.filter((_, i) => i !== idx))
  }

  return (
    <div className="space-y-3">
      {casts.map((c, i) => (
        <div key={i} className="space-y-1.5 rounded border p-2 bg-muted/20">
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-muted-foreground">Cast {i + 1}</span>
            {casts.length > 1 && (
              <Button variant="ghost" size="icon" className="h-5 w-5" onClick={() => removeCast(i)}>
                <Trash2 className="h-3 w-3 text-destructive" />
              </Button>
            )}
          </div>
          <SingleColumnSelect
            value={c.column}
            onChange={(v) => updateCast(i, "column", v)}
            columns={columns || []}
            placeholder="Select column"
          />
          <Select value={c.to_type} onValueChange={(v) => updateCast(i, "to_type", v)}>
            <SelectTrigger className="h-7 text-sm"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="int" className="text-sm">Integer</SelectItem>
              <SelectItem value="float" className="text-sm">Float</SelectItem>
              <SelectItem value="str" className="text-sm">String</SelectItem>
              <SelectItem value="category" className="text-sm">Category</SelectItem>
              <SelectItem value="bool" className="text-sm">Boolean</SelectItem>
              <SelectItem value="datetime" className="text-sm">Datetime</SelectItem>
            </SelectContent>
          </Select>
        </div>
      ))}
      <Button variant="outline" size="sm" className="w-full text-sm" onClick={addCast}>
        <Plus className="mr-1.5 h-3 w-3" /> Add Cast
      </Button>
    </div>
  )
}

// ── Outlier Remove ────────────────────────────────────────

export function OutlierRemoveConfig({
  config,
  onChange,
  columns,
}: TransformConfigProps) {
  return (
    <div className="space-y-3">
      <div className="space-y-1">
        <Label className="text-sm">Method</Label>
        <Select value={config.method || "iqr"} onValueChange={(v) => onChange("method", v)}>
          <SelectTrigger className="h-8 text-sm"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="iqr" className="text-sm">IQR — Interquartile Range (robust)</SelectItem>
            <SelectItem value="zscore" className="text-sm">Z-Score — standard deviations from mean</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-1">
        <Label className="text-sm">Threshold</Label>
        <Input
          type="number"
          step="0.1"
          value={config.threshold ?? 1.5}
          onChange={(e) => onChange("threshold", parseFloat(e.target.value) || 1.5)}
          className="h-8 text-sm"
        />
        <p className="text-[11px] text-muted-foreground">
          {config.method === "zscore" ? "Z-score threshold (default: 3.0)" : "IQR multiplier (default: 1.5)"}
        </p>
      </div>
      {(columns || []).length > 0 ? (
        <MultiColumnSelect
          label="Columns (empty = all numeric)"
          selected={(config.columns ?? "").split(",").map((s: string) => s.trim()).filter(Boolean)}
          onChange={(sel) => onChange("columns", sel.join(", "))}
          columns={columns || []}
          filterType={["integer", "float"]}
          maxHeight="150px"
        />
      ) : (
        <div className="space-y-1">
          <Label className="text-sm">Columns (comma-separated, empty = all numeric)</Label>
          <Input
            value={config.columns ?? ""}
            onChange={(e) => onChange("columns", e.target.value)}
            placeholder="Leave empty for all numeric columns"
            className="h-8 text-sm font-mono"
          />
        </div>
      )}
    </div>
  )
}

// ── Datetime Extract ──────────────────────────────────────

const DATETIME_PARTS = ["year", "month", "day", "dayofweek", "hour", "minute", "quarter", "weekofyear"]

export function DatetimeExtractConfig({
  config,
  onChange,
  columns,
}: TransformConfigProps) {
  const extract: string[] = config.extract || ["year", "month", "day", "dayofweek"]

  const togglePart = (part: string) => {
    if (extract.includes(part)) {
      onChange("extract", extract.filter((p) => p !== part))
    } else {
      onChange("extract", [...extract, part])
    }
  }

  return (
    <div className="space-y-3">
      <SingleColumnSelect
        label="Datetime Column"
        value={config.column ?? ""}
        onChange={(v) => onChange("column", v)}
        columns={columns || []}
        filterType={["datetime"]}
        placeholder="Select datetime column"
      />
      <div className="space-y-1">
        <Label className="text-sm">Extract</Label>
        <div className="flex flex-wrap gap-1.5">
          {DATETIME_PARTS.map((part) => (
            <label key={part} className="flex items-center gap-1 text-sm">
              <Checkbox checked={extract.includes(part)} onCheckedChange={() => togglePart(part)} />
              {part}
            </label>
          ))}
        </div>
        <p className="text-[11px] text-muted-foreground">New columns will be created: column_year, column_month, etc.</p>
      </div>
    </div>
  )
}

// ── Binning ───────────────────────────────────────────────

export function BinningConfig({
  config,
  onChange,
  columns,
}: TransformConfigProps) {
  return (
    <div className="space-y-3">
      <SingleColumnSelect
        label="Column"
        value={config.column ?? ""}
        onChange={(v) => onChange("column", v)}
        columns={columns || []}
        filterType={["integer", "float"]}
        placeholder="Select numeric column"
      />
      <div className="space-y-1">
        <Label className="text-sm">Number of Bins</Label>
        <Input
          type="number"
          value={config.bins ?? 5}
          onChange={(e) => onChange("bins", parseInt(e.target.value) || 5)}
          className="h-8 text-sm"
        />
      </div>
      <div className="space-y-1">
        <Label className="text-sm">Strategy</Label>
        <Select value={config.strategy || "uniform"} onValueChange={(v) => onChange("strategy", v)}>
          <SelectTrigger className="h-8 text-sm"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="uniform" className="text-sm">Uniform — equal width bins</SelectItem>
            <SelectItem value="quantile" className="text-sm">Quantile — equal count bins</SelectItem>
            <SelectItem value="kmeans" className="text-sm">KMeans — cluster-based bins</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-1">
        <Label className="text-sm">Labels (optional, comma-separated)</Label>
        <Input
          value={config.labels ?? ""}
          onChange={(e) => onChange("labels", e.target.value)}
          placeholder="e.g., low, medium, high"
          className="h-8 text-sm"
        />
        <p className="text-[11px] text-muted-foreground">Custom labels for each bin. Must match number of bins.</p>
      </div>
    </div>
  )
}

// ── Sample ───���────────────────────────────────────────────

export function SampleConfig({
  config,
  onChange,
}: Omit<TransformConfigProps, "columns">) {
  return (
    <div className="space-y-3">
      <div className="space-y-1">
        <Label className="text-sm">Number of Rows</Label>
        <Input
          type="number"
          value={config.n_rows ?? 10000}
          onChange={(e) => onChange("n_rows", parseInt(e.target.value) || 10000)}
          className="h-8 text-sm"
        />
        <p className="text-[11px] text-muted-foreground">Randomly select this many rows from the dataset</p>
      </div>
      <div className="space-y-1">
        <Label className="text-sm">Random Seed</Label>
        <Input
          type="number"
          value={config.random_seed ?? 42}
          onChange={(e) => onChange("random_seed", parseInt(e.target.value) || 42)}
          className="h-8 text-sm"
        />
        <p className="text-[11px] text-muted-foreground">Fixed seed for reproducible sampling</p>
      </div>
    </div>
  )
}

// ── Sort ──────────────────────────────────────────────────

export function SortConfig({
  config,
  onChange,
  columns,
}: TransformConfigProps) {
  return (
    <div className="space-y-3">
      <SingleColumnSelect
        label="Sort Column"
        value={config.column ?? ""}
        onChange={(v) => onChange("column", v)}
        columns={columns || []}
        placeholder="Select sort column"
      />
      <div className="flex items-center gap-2">
        <Checkbox
          checked={config.ascending ?? true}
          onCheckedChange={(v) => onChange("ascending", !!v)}
        />
        <Label className="text-sm">Ascending order</Label>
      </div>
      <p className="text-[11px] text-muted-foreground">Essential for time-series data to maintain chronological order</p>
    </div>
  )
}
