"use client"

import { useCallback, useEffect, useState } from "react"
import { Card, CardContent } from "@workspace/ui/components/card"
import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@workspace/ui/components/select"
import {
  Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList,
} from "@workspace/ui/components/command"
import { Popover, PopoverContent, PopoverTrigger } from "@workspace/ui/components/popover"
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@workspace/ui/components/table"
import { Label } from "@workspace/ui/components/label"
import { Separator } from "@workspace/ui/components/separator"
import {
  AlertTriangle, ArrowRight, Check, ChevronsUpDown, RefreshCw, Shield, Zap,
} from "lucide-react"
import { authFetch } from "@/features/auth/auth-fetch"

const BASE = "/api/v1/standards"

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Dictionary = {
  id: number; dict_name: string; version: string | null
}

type ColumnTermStatus = {
  schema_id: number
  column_name: string
  column_type: string
  native_type: string | null
  mapping_id: number | null
  mapping_type: string | null
  term_id: number | null
  term_name: string | null
  term_physical_name: string | null
  term_data_type: string | null
  term_data_length: number | null
}

type ComplianceStats = {
  total_columns: number
  matched: number
  similar: number
  violation: number
  unmapped: number
  compliance_rate: number
}

type DatasetTermMapping = {
  dataset_id: number
  dictionary_id: number
  columns: ColumnTermStatus[]
  compliance: ComplianceStats
}

type AutoMapResult = {
  created: number; updated: number; matched: number
  similar: number; violation: number; unmapped: number
}

type TermSummary = {
  id: number; term_name: string; physical_name: string
  domain_name: string | null; domain_data_type: string | null
}

type Props = {
  datasetId: number
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function TermsTab({ datasetId }: Props) {
  const [dictionaries, setDictionaries] = useState<Dictionary[]>([])
  const [selectedDictId, setSelectedDictId] = useState<number | null>(null)
  const [mapping, setMapping] = useState<DatasetTermMapping | null>(null)
  const [loading, setLoading] = useState(false)
  const [autoMapping, setAutoMapping] = useState(false)
  const [autoMapResult, setAutoMapResult] = useState<AutoMapResult | null>(null)

  // Load dictionaries
  useEffect(() => {
    authFetch(`${BASE}/dictionaries`)
      .then(r => r.json())
      .then((data: Dictionary[]) => {
        setDictionaries(data)
        if (data.length > 0 && !selectedDictId) setSelectedDictId(data[0].id)
      })
      .catch(() => {})
  }, [selectedDictId])

  // Load mapping when dictionary changes
  const loadMapping = useCallback(async () => {
    if (!selectedDictId) return
    setLoading(true)
    try {
      const resp = await authFetch(
        `${BASE}/mappings/dataset?dictionary_id=${selectedDictId}&dataset_id=${datasetId}`
      )
      if (resp.ok) setMapping(await resp.json())
    } catch { /* */ } finally {
      setLoading(false)
    }
  }, [selectedDictId, datasetId])

  useEffect(() => { loadMapping() }, [loadMapping])

  // Auto map
  const handleAutoMap = async () => {
    if (!selectedDictId) return
    setAutoMapping(true)
    setAutoMapResult(null)
    try {
      const resp = await authFetch(
        `${BASE}/mappings/auto-map?dictionary_id=${selectedDictId}&dataset_id=${datasetId}`,
        { method: "POST" },
      )
      if (resp.ok) {
        const result = await resp.json()
        setAutoMapResult(result)
        await loadMapping()
      }
    } catch { /* */ } finally {
      setAutoMapping(false)
    }
  }

  // Manual mapping
  const handleManualMap = async (schemaId: number, termId: number) => {
    await authFetch(`${BASE}/mappings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        term_id: termId,
        dataset_id: datasetId,
        schema_id: schemaId,
        mapping_type: "SIMILAR",
      }),
    })
    await loadMapping()
  }

  // Delete mapping
  const handleDeleteMapping = async (mappingId: number) => {
    await authFetch(`${BASE}/mappings/${mappingId}`, { method: "DELETE" })
    await loadMapping()
  }

  const stats = mapping?.compliance

  return (
    <div className="space-y-4">
      {/* Header: Dictionary selector + Auto Map */}
      <div className="flex items-center gap-3">
        <Label className="text-sm">Dictionary:</Label>
        <Select
          value={selectedDictId ? String(selectedDictId) : ""}
          onValueChange={v => { setSelectedDictId(Number(v)); setAutoMapResult(null) }}
        >
          <SelectTrigger className="w-64 h-9">
            <SelectValue placeholder="Select dictionary..." />
          </SelectTrigger>
          <SelectContent>
            {dictionaries.map(d => (
              <SelectItem key={d.id} value={String(d.id)}>
                {d.dict_name} {d.version && `(${d.version})`}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Button
          variant="outline"
          size="sm"
          onClick={handleAutoMap}
          disabled={autoMapping || !selectedDictId}
          className="gap-1.5"
        >
          <Zap className="h-3.5 w-3.5" />
          {autoMapping ? "Mapping..." : "Auto Map"}
        </Button>

        {autoMapResult && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Check className="h-3.5 w-3.5 text-green-500" />
            Created: {autoMapResult.created}, Updated: {autoMapResult.updated}
          </div>
        )}
      </div>

      {/* Compliance bar */}
      {stats && stats.total_columns > 0 && (
        <Card>
          <CardContent className="py-3 px-4">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <Shield className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm font-medium">Compliance</span>
              </div>
              <div className="flex-1">
                <div className="w-full bg-muted rounded-full h-2.5">
                  <div
                    className={`h-2.5 rounded-full transition-all ${
                      stats.compliance_rate >= 80 ? "bg-green-500"
                        : stats.compliance_rate >= 50 ? "bg-amber-500"
                          : "bg-red-500"
                    }`}
                    style={{ width: `${stats.compliance_rate}%` }}
                  />
                </div>
              </div>
              <span className="text-sm font-bold min-w-[48px] text-right">
                {stats.compliance_rate}%
              </span>
              <Separator orientation="vertical" className="h-5" />
              <div className="flex items-center gap-3 text-xs">
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-green-500" />
                  {stats.matched}
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-amber-500" />
                  {stats.similar}
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-red-500" />
                  {stats.violation}
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-gray-300" />
                  {stats.unmapped}
                </span>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Column mapping table */}
      {loading ? (
        <Card>
          <CardContent className="flex items-center justify-center py-12">
            <p className="text-sm text-muted-foreground">Loading...</p>
          </CardContent>
        </Card>
      ) : !mapping || mapping.columns.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12 gap-3">
            <Shield className="h-10 w-10 text-muted-foreground/40" />
            <p className="text-sm text-muted-foreground">
              {selectedDictId
                ? "No schema columns found. Run Auto Map after adding schema."
                : "Select a dictionary to view term mappings."}
            </p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-10" />
                  <TableHead>Column</TableHead>
                  <TableHead className="w-32">Actual Type</TableHead>
                  <TableHead className="w-8" />
                  <TableHead>Standard Term</TableHead>
                  <TableHead className="w-36">Standard Type</TableHead>
                  <TableHead className="w-24">Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {mapping.columns.map(col => (
                  <TableRow key={col.schema_id}>
                    {/* Status icon */}
                    <TableCell className="text-center">
                      <StatusIcon type={col.mapping_type} />
                    </TableCell>

                    {/* Column name */}
                    <TableCell>
                      <code className="text-sm font-mono" style={{ fontFamily: "var(--font-d2coding), 'D2Coding', Consolas, monospace" }}>{col.column_name}</code>
                    </TableCell>

                    {/* Actual type */}
                    <TableCell>
                      <span className="text-sm text-muted-foreground font-mono" style={{ fontFamily: "var(--font-d2coding), 'D2Coding', Consolas, monospace" }}>
                        {col.native_type || col.column_type}
                      </span>
                    </TableCell>

                    {/* Arrow */}
                    <TableCell>
                      {col.term_id && (
                        <ArrowRight className="h-3.5 w-3.5 text-muted-foreground" />
                      )}
                    </TableCell>

                    {/* Standard term */}
                    <TableCell>
                      {col.term_name ? (
                        <div>
                          <span className="text-sm font-medium">{col.term_name}</span>
                          <span className="text-sm text-muted-foreground ml-1.5">
                            ({col.term_physical_name})
                          </span>
                        </div>
                      ) : (
                        <ManualMapPicker
                          dictionaryId={selectedDictId!}
                          schemaId={col.schema_id}
                          columnName={col.column_name}
                          onSelect={(termId) => handleManualMap(col.schema_id, termId)}
                        />
                      )}
                    </TableCell>

                    {/* Standard type */}
                    <TableCell>
                      {col.term_data_type && (
                        <code className="text-sm" style={{ fontFamily: "var(--font-d2coding), 'D2Coding', Consolas, monospace" }}>
                          {col.term_data_type}
                          {col.term_data_length && `(${col.term_data_length})`}
                        </code>
                      )}
                    </TableCell>

                    {/* Status badge */}
                    <TableCell>
                      <div className="flex items-center gap-1">
                        <MappingBadge type={col.mapping_type} />
                        {col.mapping_id && (
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-5 w-5 opacity-0 group-hover:opacity-100"
                            onClick={() => handleDeleteMapping(col.mapping_id!)}
                            title="Remove mapping"
                          >
                            <RefreshCw className="h-3 w-3" />
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Violations summary */}
      {mapping && mapping.columns.some(c => c.mapping_type === "VIOLATION") && (
        <Card className="border-red-200 dark:border-red-900">
          <CardContent className="py-3 px-4">
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle className="h-4 w-4 text-red-500" />
              <span className="text-sm font-medium text-red-600 dark:text-red-400">
                Standard Violations
              </span>
            </div>
            <div className="space-y-1">
              {mapping.columns
                .filter(c => c.mapping_type === "VIOLATION")
                .map(c => (
                  <p key={c.schema_id} className="text-xs text-muted-foreground">
                    <code className="font-mono text-red-600 dark:text-red-400">{c.column_name}</code>
                    : {c.native_type || c.column_type} → standard{" "}
                    <code className="font-mono">
                      {c.term_data_type}{c.term_data_length && `(${c.term_data_length})`}
                    </code>
                    . Type mismatch with term "{c.term_name}".
                  </p>
                ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Manual Map Picker
// ---------------------------------------------------------------------------

function ManualMapPicker({
  dictionaryId,
  schemaId,
  columnName,
  onSelect,
}: {
  dictionaryId: number
  schemaId: number
  columnName: string
  onSelect: (termId: number) => void
}) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState("")
  const [terms, setTerms] = useState<TermSummary[]>([])

  useEffect(() => {
    if (!open) return
    const params = new URLSearchParams({ dictionary_id: String(dictionaryId) })
    if (search) params.set("search", search)
    authFetch(`${BASE}/terms?${params}`)
      .then(r => r.json())
      .then(setTerms)
      .catch(() => {})
  }, [open, search, dictionaryId])

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" className="h-7 text-sm gap-1 font-normal">
          <ChevronsUpDown className="h-3 w-3" />
          Map to term...
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[400px] p-0" align="start">
        <Command shouldFilter={false}>
          <CommandInput
            placeholder="Search terms..."
            value={search}
            onValueChange={setSearch}
          />
          <CommandList>
            <CommandEmpty>No terms found.</CommandEmpty>
            <CommandGroup>
              {terms.map(t => (
                <CommandItem
                  key={t.id}
                  value={String(t.id)}
                  onSelect={() => {
                    onSelect(t.id)
                    setOpen(false)
                  }}
                >
                  <div className="flex items-center gap-2 w-full">
                    <span className="font-medium">{t.term_name}</span>
                    <code className="text-[10px] text-muted-foreground">{t.physical_name}</code>
                    {t.domain_name && (
                      <span className="ml-auto text-[10px] text-muted-foreground">
                        {t.domain_name} ({t.domain_data_type})
                      </span>
                    )}
                  </div>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function StatusIcon({ type }: { type: string | null }) {
  if (type === "MATCHED") return <span className="flex justify-center"><span className="w-2.5 h-2.5 rounded-full bg-green-500" /></span>
  if (type === "SIMILAR") return <span className="flex justify-center"><span className="w-2.5 h-2.5 rounded-full bg-amber-500" /></span>
  if (type === "VIOLATION") return <span className="flex justify-center"><span className="w-2.5 h-2.5 rounded-full bg-red-500" /></span>
  return <span className="flex justify-center"><span className="w-2.5 h-2.5 rounded-full bg-gray-200 dark:bg-gray-700" /></span>
}

function MappingBadge({ type }: { type: string | null }) {
  if (type === "MATCHED") return <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200 text-xs px-2 py-0.5 border-0">Matched</Badge>
  if (type === "SIMILAR") return <Badge className="bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200 text-xs px-2 py-0.5 border-0">Similar</Badge>
  if (type === "VIOLATION") return <Badge className="bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200 text-xs px-2 py-0.5 border-0">Violation</Badge>
  return <Badge variant="outline" className="text-xs px-2 py-0.5 text-muted-foreground">Unmapped</Badge>
}
