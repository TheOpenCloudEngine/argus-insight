"use client"

import { useCallback, useEffect, useState } from "react"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@workspace/ui/components/dialog"
import { Button } from "@workspace/ui/components/button"
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"
import { Textarea } from "@workspace/ui/components/textarea"
import { Checkbox } from "@workspace/ui/components/checkbox"
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@workspace/ui/components/select"
import {
  Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList,
} from "@workspace/ui/components/command"
import { Popover, PopoverContent, PopoverTrigger } from "@workspace/ui/components/popover"
import { Badge } from "@workspace/ui/components/badge"
import { Separator } from "@workspace/ui/components/separator"
import { Check, ChevronsUpDown, Plus, X } from "lucide-react"
import { authFetch } from "@/features/auth/auth-fetch"

const BASE = "/api/v1"

type EditRule = {
  id: number
  rule_name: string
  scope_type: string
  scope_id: number | null
  trigger_type: string
  trigger_config: string
  severity_override: string | null
  channels: string
  notify_owners: string
  webhook_url: string | null
  subscribers: string | null
  description: string | null
}

type Props = {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreated: () => void
  presetScope?: { type: string; id: number; name: string }
  editRule?: EditRule | null
}

type Tag = { id: number; name: string; color: string }
type DatasetSummary = { id: number; name: string; platform_type: string; platform_name: string }
type Platform = { id: number; platform_id: string; name: string; type: string }
type LineageSummary = {
  id: number
  source_dataset_name: string | null
  target_dataset_name: string | null
  source_platform_type: string | null
  target_platform_type: string | null
}

export function RuleCreateDialog({ open, onOpenChange, onCreated, presetScope, editRule }: Props) {
  const isEdit = !!editRule
  const [step, setStep] = useState(1)

  // Step 1
  const [ruleName, setRuleName] = useState("")
  const [scopeType, setScopeType] = useState("ALL")
  const [scopeId, setScopeId] = useState<number | null>(null)
  const [triggerType, setTriggerType] = useState("ANY")
  const [changeTypes, setChangeTypes] = useState<string[]>(["DROP", "MODIFY"])
  const [watchColumns, setWatchColumns] = useState("")
  const [severityOverride, setSeverityOverride] = useState("auto")

  // Step 2
  const [channels, setChannels] = useState<string[]>(["IN_APP"])
  const [webhookUrl, setWebhookUrl] = useState("")
  const [subscribers, setSubscribers] = useState("")
  const [notifyOwners, setNotifyOwners] = useState(true)
  const [description, setDescription] = useState("")

  // Lookup data
  const [tags, setTags] = useState<Tag[]>([])
  const [platforms, setPlatforms] = useState<Platform[]>([])
  const [datasets, setDatasets] = useState<DatasetSummary[]>([])
  const [lineages, setLineages] = useState<LineageSummary[]>([])
  const [scopePopoverOpen, setScopePopoverOpen] = useState(false)
  const [scopeSearch, setScopeSearch] = useState("")

  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Reset on open — populate from editRule if editing
  useEffect(() => {
    if (!open) return
    setStep(1)
    setError(null)
    if (editRule) {
      setRuleName(editRule.rule_name)
      setScopeType(editRule.scope_type)
      setScopeId(editRule.scope_id)
      setTriggerType(editRule.trigger_type)
      const config = editRule.trigger_config ? JSON.parse(editRule.trigger_config) : {}
      setChangeTypes(config.change_types || ["DROP", "MODIFY"])
      setWatchColumns((config.columns || []).join(", "))
      setSeverityOverride(editRule.severity_override || "auto")
      setChannels(editRule.channels ? editRule.channels.split(",") : ["IN_APP"])
      setWebhookUrl(editRule.webhook_url || "")
      setSubscribers(editRule.subscribers || "")
      setNotifyOwners(editRule.notify_owners === "true")
      setDescription(editRule.description || "")
    } else {
      setRuleName("")
      setScopeType(presetScope?.type || "ALL")
      setScopeId(presetScope?.id || null)
      setTriggerType(presetScope?.type === "LINEAGE" ? "MAPPING_BROKEN" : "ANY")
      setChangeTypes(["DROP", "MODIFY"])
      setWatchColumns("")
      setSeverityOverride("auto")
      setChannels(["IN_APP"])
      setWebhookUrl("")
      setSubscribers("")
      setNotifyOwners(true)
      setDescription("")
    }
  }, [open, presetScope, editRule])

  // Load lookup data
  useEffect(() => {
    if (!open) return
    authFetch(`${BASE}/catalog/tags`).then(r => r.json()).then(setTags).catch(() => {})
    authFetch(`${BASE}/catalog/platforms`).then(r => r.json()).then(setPlatforms).catch(() => {})
  }, [open])

  // Load scope-specific data
  useEffect(() => {
    if (!open) return
    if (scopeType === "DATASET") {
      const params = new URLSearchParams({ page_size: "100" })
      if (scopeSearch) params.set("search", scopeSearch)
      authFetch(`${BASE}/catalog/datasets?${params}`)
        .then(r => r.json())
        .then(d => setDatasets(d.items || []))
        .catch(() => {})
    } else if (scopeType === "LINEAGE") {
      authFetch(`${BASE}/catalog/lineage`)
        .then(r => r.json())
        .then(setLineages)
        .catch(() => {})
    }
  }, [open, scopeType, scopeSearch])

  const toggleChangeType = (type: string) => {
    setChangeTypes(prev =>
      prev.includes(type) ? prev.filter(t => t !== type) : [...prev, type]
    )
  }

  const toggleChannel = (ch: string) => {
    setChannels(prev =>
      prev.includes(ch) ? prev.filter(c => c !== ch) : [...prev, ch]
    )
  }

  // Scope display name
  const scopeDisplayName = useCallback(() => {
    if (scopeType === "ALL") return "All datasets"
    if (scopeType === "TAG" && scopeId) {
      const tag = tags.find(t => t.id === scopeId)
      return tag ? `Tag: ${tag.name}` : `Tag ID: ${scopeId}`
    }
    if (scopeType === "DATASET" && scopeId) {
      const ds = datasets.find(d => d.id === scopeId)
      return ds ? `${ds.platform_type}.${ds.name}` : `Dataset ID: ${scopeId}`
    }
    if (scopeType === "LINEAGE" && scopeId) {
      const l = lineages.find(l => l.id === scopeId)
      return l ? `${l.source_platform_type}.${l.source_dataset_name} → ${l.target_platform_type}.${l.target_dataset_name}` : `Lineage ID: ${scopeId}`
    }
    if (scopeType === "PLATFORM" && scopeId) {
      const p = platforms.find(p => p.id === scopeId)
      return p ? `Platform: ${p.name}` : `Platform ID: ${scopeId}`
    }
    return "Select..."
  }, [scopeType, scopeId, tags, datasets, lineages, platforms])

  const handleSave = async () => {
    if (!ruleName.trim()) return
    setSaving(true)
    setError(null)

    const triggerConfig: Record<string, unknown> = {}
    if (triggerType === "SCHEMA_CHANGE") {
      triggerConfig.change_types = changeTypes
    } else if (triggerType === "COLUMN_WATCH") {
      triggerConfig.columns = watchColumns.split(",").map(c => c.trim()).filter(Boolean)
      triggerConfig.change_types = changeTypes
    }

    const body = {
      rule_name: ruleName,
      description: description || null,
      scope_type: scopeType,
      scope_id: scopeType === "ALL" ? null : scopeId,
      trigger_type: triggerType,
      trigger_config: JSON.stringify(triggerConfig),
      severity_override: severityOverride === "auto" ? null : severityOverride,
      channels: channels.join(","),
      notify_owners: notifyOwners ? "true" : "false",
      webhook_url: channels.includes("WEBHOOK") ? webhookUrl || null : null,
      subscribers: subscribers || null,
    }

    try {
      const url = isEdit ? `${BASE}/alerts/rules/${editRule!.id}` : `${BASE}/alerts/rules`
      const method = isEdit ? "PUT" : "POST"
      const resp = await authFetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      })
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}))
        throw new Error(data.detail || `HTTP ${resp.status}`)
      }
      onCreated()
      onOpenChange(false)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save")
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit Alert Rule" : "Create Alert Rule"}</DialogTitle>
        </DialogHeader>

        {/* Step indicator */}
        <div className="flex items-center gap-2 text-sm mb-2">
          <StepDot n={1} label="What & When" current={step} />
          <div className="h-px flex-1 bg-border" />
          <StepDot n={2} label="Who & How" current={step} />
        </div>

        {error && (
          <p className="text-sm text-destructive bg-destructive/10 rounded px-3 py-2">{error}</p>
        )}

        {/* ===== Step 1: What to Watch + Trigger ===== */}
        {step === 1 && (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-sm">Rule Name</Label>
              <Input
                value={ruleName}
                onChange={e => setRuleName(e.target.value)}
                placeholder="PII 데이터 컬럼 삭제 감시"
                className="h-9"
              />
            </div>

            <Separator />
            <Label className="text-sm font-medium">Scope (감시 대상)</Label>

            {/* Scope type buttons */}
            <div className="flex gap-1.5 flex-wrap">
              {["DATASET", "TAG", "LINEAGE", "PLATFORM", "ALL"].map(t => (
                <Button
                  key={t}
                  variant={scopeType === t ? "default" : "outline"}
                  size="sm"
                  className="text-sm h-8"
                  onClick={() => { setScopeType(t); setScopeId(null) }}
                >
                  {t === "DATASET" && "Dataset"}
                  {t === "TAG" && "Tag"}
                  {t === "LINEAGE" && "Lineage"}
                  {t === "PLATFORM" && "Platform"}
                  {t === "ALL" && "All"}
                </Button>
              ))}
            </div>

            {/* Scope target selector */}
            {scopeType === "TAG" && (
              <Select value={scopeId ? String(scopeId) : ""} onValueChange={v => setScopeId(Number(v))}>
                <SelectTrigger className="h-9"><SelectValue placeholder="Select tag..." /></SelectTrigger>
                <SelectContent>
                  {tags.map(t => (
                    <SelectItem key={t.id} value={String(t.id)}>
                      <span className="inline-block w-2 h-2 rounded-full mr-1.5" style={{ backgroundColor: t.color }} />
                      {t.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}

            {scopeType === "PLATFORM" && (
              <Select value={scopeId ? String(scopeId) : ""} onValueChange={v => setScopeId(Number(v))}>
                <SelectTrigger className="h-9"><SelectValue placeholder="Select platform..." /></SelectTrigger>
                <SelectContent>
                  {platforms.map(p => (
                    <SelectItem key={p.id} value={String(p.id)}>{p.name} ({p.type})</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}

            {scopeType === "DATASET" && (
              <Popover open={scopePopoverOpen} onOpenChange={setScopePopoverOpen}>
                <PopoverTrigger asChild>
                  <Button variant="outline" className="w-full justify-between h-9 font-normal text-sm">
                    {scopeId ? scopeDisplayName() : "Search and select dataset..."}
                    <ChevronsUpDown className="ml-2 h-3.5 w-3.5 opacity-50" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-[480px] p-0" align="start">
                  <Command shouldFilter={false}>
                    <CommandInput placeholder="Search..." value={scopeSearch} onValueChange={setScopeSearch} />
                    <CommandList>
                      <CommandEmpty>No datasets found.</CommandEmpty>
                      <CommandGroup>
                        {datasets.map(d => (
                          <CommandItem key={d.id} value={String(d.id)} onSelect={() => { setScopeId(d.id); setScopePopoverOpen(false) }}>
                            <Check className={`mr-2 h-3.5 w-3.5 ${scopeId === d.id ? "opacity-100" : "opacity-0"}`} />
                            <Badge variant="outline" className="mr-1.5 text-[9px] px-1 py-0">{d.platform_type}</Badge>
                            <span className="truncate">{d.name}</span>
                          </CommandItem>
                        ))}
                      </CommandGroup>
                    </CommandList>
                  </Command>
                </PopoverContent>
              </Popover>
            )}

            {scopeType === "LINEAGE" && (
              <Select value={scopeId ? String(scopeId) : ""} onValueChange={v => setScopeId(Number(v))}>
                <SelectTrigger className="h-9 text-sm"><SelectValue placeholder="Select lineage..." /></SelectTrigger>
                <SelectContent>
                  {lineages.map(l => (
                    <SelectItem key={l.id} value={String(l.id)} className="text-sm">
                      {l.source_platform_type}.{l.source_dataset_name} → {l.target_platform_type}.{l.target_dataset_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}

            <Separator />
            <Label className="text-sm font-medium">Trigger (트리거 조건)</Label>

            <Select value={triggerType} onValueChange={setTriggerType}>
              <SelectTrigger className="h-9"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="ANY">Any Change (모든 변경)</SelectItem>
                <SelectItem value="SCHEMA_CHANGE">Schema Change (변경 유형 선택)</SelectItem>
                <SelectItem value="COLUMN_WATCH">Column Watch (특정 컬럼 감시)</SelectItem>
                <SelectItem value="MAPPING_BROKEN">Mapping Broken (매핑 컬럼 변경)</SelectItem>
              </SelectContent>
            </Select>

            {(triggerType === "SCHEMA_CHANGE" || triggerType === "COLUMN_WATCH") && (
              <div className="flex items-center gap-4">
                <Label className="text-sm text-muted-foreground">Change Types:</Label>
                {["DROP", "MODIFY", "ADD"].map(ct => (
                  <label key={ct} className="flex items-center gap-1.5 text-sm">
                    <Checkbox
                      checked={changeTypes.includes(ct)}
                      onCheckedChange={() => toggleChangeType(ct)}
                    />
                    {ct}
                  </label>
                ))}
              </div>
            )}

            {triggerType === "COLUMN_WATCH" && (
              <div className="space-y-1.5">
                <Label className="text-sm">Watch Columns (콤마 구분)</Label>
                <Input
                  value={watchColumns}
                  onChange={e => setWatchColumns(e.target.value)}
                  placeholder="amount, currency, status"
                  className="h-9 text-sm"
                />
              </div>
            )}

            <div className="space-y-1.5">
              <Label className="text-sm">Severity</Label>
              <Select value={severityOverride} onValueChange={setSeverityOverride}>
                <SelectTrigger className="h-9"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="auto">Auto (자동 판정)</SelectItem>
                  <SelectItem value="BREAKING">BREAKING (강제)</SelectItem>
                  <SelectItem value="WARNING">WARNING (강제)</SelectItem>
                  <SelectItem value="INFO">INFO (강제)</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="flex justify-end">
              <Button onClick={() => setStep(2)} disabled={!ruleName.trim() || (scopeType !== "ALL" && !scopeId)}>
                Next
              </Button>
            </div>
          </div>
        )}

        {/* ===== Step 2: Who to Notify ===== */}
        {step === 2 && (
          <div className="space-y-4">
            {/* Summary */}
            <div className="rounded-lg border px-4 py-3 bg-muted/30 text-sm">
              <p className="font-medium">{ruleName}</p>
              <p className="text-sm text-muted-foreground mt-1">
                Scope: {scopeType} {scopeId ? `(${scopeDisplayName()})` : ""} | Trigger: {triggerType}
              </p>
            </div>

            <Label className="text-sm font-medium">Channels (알림 채널)</Label>
            <div className="flex items-center gap-4">
              {["IN_APP", "WEBHOOK", "EMAIL"].map(ch => (
                <label key={ch} className="flex items-center gap-1.5 text-sm">
                  <Checkbox
                    checked={channels.includes(ch)}
                    onCheckedChange={() => toggleChannel(ch)}
                  />
                  {ch === "IN_APP" ? "In-App" : ch === "WEBHOOK" ? "Webhook" : "Email"}
                </label>
              ))}
            </div>

            {channels.includes("WEBHOOK") && (
              <div className="space-y-1.5">
                <Label className="text-sm">Webhook URL</Label>
                <Input
                  value={webhookUrl}
                  onChange={e => setWebhookUrl(e.target.value)}
                  placeholder="https://hooks.slack.com/services/..."
                  className="h-9 text-sm"
                />
              </div>
            )}

            <div className="space-y-1.5">
              <Label className="text-sm">Subscribers (콤마 구분)</Label>
              <Textarea
                value={subscribers}
                onChange={e => setSubscribers(e.target.value)}
                placeholder="security-team@company.com, dpo@company.com"
                rows={2}
                className="text-sm"
              />
            </div>

            <label className="flex items-center gap-2 text-sm">
              <Checkbox
                checked={notifyOwners}
                onCheckedChange={(v) => setNotifyOwners(!!v)}
              />
              Also notify dataset owners
            </label>

            <div className="space-y-1.5">
              <Label className="text-sm">Description (선택)</Label>
              <Textarea
                value={description}
                onChange={e => setDescription(e.target.value)}
                placeholder="이 규칙의 목적을 설명하세요..."
                rows={2}
                className="text-sm"
              />
            </div>

            <Separator />
            <div className="flex justify-between">
              <Button variant="outline" onClick={() => setStep(1)}>Back</Button>
              <Button onClick={handleSave} disabled={saving}>
                {saving ? "Saving..." : isEdit ? "Update Rule" : "Save Rule"}
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

function StepDot({ n, label, current }: { n: number; label: string; current: number }) {
  const done = current > n
  const active = current === n
  return (
    <div className="flex items-center gap-1.5">
      <div className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-medium ${
        done || active ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
      }`}>
        {done ? <Check className="h-3 w-3" /> : n}
      </div>
      <span className={active ? "text-foreground font-medium" : "text-muted-foreground"}>{label}</span>
    </div>
  )
}
