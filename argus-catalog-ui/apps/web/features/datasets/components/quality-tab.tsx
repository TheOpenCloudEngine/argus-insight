"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { Card, CardContent } from "@workspace/ui/components/card"
import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@workspace/ui/components/select"
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@workspace/ui/components/table"
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@workspace/ui/components/dialog"
import { Separator } from "@workspace/ui/components/separator"
import { AlertTriangle, CheckCircle, Play, Plus, Shield, Trash2, XCircle } from "lucide-react"
import { authFetch } from "@/features/auth/auth-fetch"

const BASE = "/api/v1/quality"

type QualityRule = {
  id: number; rule_name: string; check_type: string; column_name: string | null
  expected_value: string | null; threshold: number; severity: string; is_active: string
}

type QualityResult = {
  id: number; rule_id: number; rule_name: string | null; check_type: string | null
  column_name: string | null; passed: string; actual_value: string | null
  detail: string | null; severity: string | null; checked_at: string
}

type QualityScore = { score: number; total_rules: number; passed_rules: number; failed_rules: number }

type ColumnProfile = {
  column_name: string; column_type: string; total_count: number
  null_count: number; null_percent: number; unique_count: number; unique_percent: number
  min_value: string | null; max_value: string | null; mean_value: number | null
}

type Props = { datasetId: number }

export function QualityTab({ datasetId }: Props) {
  const [rules, setRules] = useState<QualityRule[]>([])
  const [results, setResults] = useState<QualityResult[]>([])
  const [score, setScore] = useState<QualityScore | null>(null)
  const [profile, setProfile] = useState<ColumnProfile[]>([])
  const [loading, setLoading] = useState(false)
  const [running, setRunning] = useState(false)
  const [profiling, setProfiling] = useState(false)
  const [addOpen, setAddOpen] = useState(false)

  // Add rule form
  const [ruleName, setRuleName] = useState("")
  const [checkType, setCheckType] = useState("NOT_NULL")
  const [columnName, setColumnName] = useState("")
  const [expectedValue, setExpectedValue] = useState("")
  const [threshold, setThreshold] = useState("100")
  const [severity, setSeverity] = useState("WARNING")

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const [rulesResp, resultsResp, scoreResp, profileResp] = await Promise.all([
        authFetch(`${BASE}/rules?dataset_id=${datasetId}`),
        authFetch(`${BASE}/datasets/${datasetId}/results`),
        authFetch(`${BASE}/datasets/${datasetId}/score`).catch(() => null),
        authFetch(`${BASE}/datasets/${datasetId}/profile`).catch(() => null),
      ])
      if (rulesResp.ok) setRules(await rulesResp.json())
      if (resultsResp.ok) setResults(await resultsResp.json())
      if (scoreResp?.ok) setScore(await scoreResp.json())
      if (profileResp?.ok) {
        const data = await profileResp.json()
        setProfile(data.columns || [])
      }
    } catch { /* */ } finally { setLoading(false) }
  }, [datasetId])

  useEffect(() => { fetchData() }, [fetchData])

  const runCheck = async () => {
    setRunning(true)
    try {
      const resp = await authFetch(`${BASE}/datasets/${datasetId}/check`, { method: "POST" })
      if (resp.ok) await fetchData()
    } catch { /* */ } finally { setRunning(false) }
  }

  const runProfile = async () => {
    setProfiling(true)
    try {
      const resp = await authFetch(`${BASE}/datasets/${datasetId}/profile`, { method: "POST" })
      if (resp.ok) await fetchData()
    } catch { /* */ } finally { setProfiling(false) }
  }

  const addRule = async () => {
    await authFetch(`${BASE}/rules`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        dataset_id: datasetId,
        rule_name: ruleName,
        check_type: checkType,
        column_name: columnName || null,
        expected_value: expectedValue || null,
        threshold: Number(threshold),
        severity,
      }),
    })
    setAddOpen(false)
    setRuleName(""); setColumnName(""); setExpectedValue(""); setThreshold("100")
    fetchData()
  }

  const deleteRule = async (ruleId: number) => {
    await authFetch(`${BASE}/rules/${ruleId}`, { method: "DELETE" })
    fetchData()
  }

  const pct = score?.score ?? 0

  return (
    <div className="space-y-4">
      {/* Score bar + action buttons */}
      <Card>
        <CardContent className="py-3 px-4">
          <div className="flex items-center gap-4">
            <Shield className="h-5 w-5 text-muted-foreground" />
            <div className="flex-1">
              <div className="flex items-center gap-3 mb-1">
                <span className="text-sm font-medium">Quality Score</span>
                <span className="text-lg font-bold">{score ? `${pct}%` : "—"}</span>
              </div>
              <div className="w-full bg-muted rounded-full h-2.5">
                <div className={`h-2.5 rounded-full transition-all ${
                  pct >= 80 ? "bg-green-500" : pct >= 50 ? "bg-amber-500" : "bg-red-500"
                }`} style={{ width: `${pct}%` }} />
              </div>
            </div>
            <Separator orientation="vertical" className="h-8" />
            {score && (
              <div className="flex items-center gap-3 text-sm">
                <span className="flex items-center gap-1"><CheckCircle className="h-3.5 w-3.5 text-green-500" />{score.passed_rules}</span>
                <span className="flex items-center gap-1"><XCircle className="h-3.5 w-3.5 text-red-500" />{score.failed_rules}</span>
                <span className="text-muted-foreground">/ {score.total_rules} rules</span>
              </div>
            )}
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={runProfile} disabled={profiling}>
                {profiling ? "Profiling..." : "Profile"}
              </Button>
              <Button variant="outline" size="sm" onClick={runCheck} disabled={running}>
                <Play className="h-3.5 w-3.5 mr-1" />
                {running ? "Running..." : "Run Check"}
              </Button>
              <Button variant="outline" size="sm" onClick={() => setAddOpen(true)}>
                <Plus className="h-3.5 w-3.5 mr-1" />Add Rule
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Results table */}
      {results.length > 0 && (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-16">Status</TableHead>
                  <TableHead>Rule</TableHead>
                  <TableHead className="w-32">Check Type</TableHead>
                  <TableHead className="w-32">Column</TableHead>
                  <TableHead className="w-28">Actual</TableHead>
                  <TableHead>Detail</TableHead>
                  <TableHead className="w-20">Severity</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {results.map(r => (
                  <TableRow key={r.id}>
                    <TableCell>
                      {r.passed === "true"
                        ? <CheckCircle className="h-4 w-4 text-green-500" />
                        : <XCircle className="h-4 w-4 text-red-500" />}
                    </TableCell>
                    <TableCell className="font-medium text-sm">{r.rule_name}</TableCell>
                    <TableCell><Badge variant="outline" className="text-sm">{r.check_type}</Badge></TableCell>
                    <TableCell className="text-sm text-muted-foreground">{r.column_name || "—"}</TableCell>
                    <TableCell className="text-sm font-mono">{r.actual_value || "—"}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">{r.detail}</TableCell>
                    <TableCell><SeverityBadge severity={r.severity || "INFO"} /></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Rules list */}
      {rules.length > 0 && (
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-medium">Quality Rules ({rules.length})</span>
            </div>
            <div className="space-y-2">
              {rules.map(rule => (
                <div key={rule.id} className="flex items-center justify-between text-sm border rounded px-3 py-2">
                  <div className="flex items-center gap-3">
                    <Badge variant="outline">{rule.check_type}</Badge>
                    <span className="font-medium">{rule.rule_name}</span>
                    {rule.column_name && <span className="text-muted-foreground font-mono">{rule.column_name}</span>}
                    <span className="text-muted-foreground">threshold: {rule.threshold}%</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <SeverityBadge severity={rule.severity} />
                    <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => deleteRule(rule.id)}>
                      <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Profile summary */}
      {profile.length > 0 && (
        <Card>
          <CardContent className="p-0">
            <div className="px-4 py-3 border-b">
              <span className="text-sm font-medium">Data Profile</span>
            </div>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Column</TableHead>
                  <TableHead className="w-20">Type</TableHead>
                  <TableHead className="w-20">NULLs</TableHead>
                  <TableHead className="w-20">Unique</TableHead>
                  <TableHead className="w-28">Min</TableHead>
                  <TableHead className="w-28">Max</TableHead>
                  <TableHead className="w-20">Mean</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {profile.map(cp => (
                  <TableRow key={cp.column_name}>
                    <TableCell className="font-medium font-mono text-sm">{cp.column_name}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">{cp.column_type}</TableCell>
                    <TableCell className={`text-sm ${cp.null_percent > 5 ? "text-red-500 font-medium" : ""}`}>
                      {cp.null_percent}%
                    </TableCell>
                    <TableCell className="text-sm">{cp.unique_percent}%</TableCell>
                    <TableCell className="text-sm font-mono">{cp.min_value ?? "—"}</TableCell>
                    <TableCell className="text-sm font-mono">{cp.max_value ?? "—"}</TableCell>
                    <TableCell className="text-sm font-mono">{cp.mean_value?.toFixed(2) ?? "—"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Empty state */}
      {rules.length === 0 && results.length === 0 && !loading && (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12 gap-3">
            <Shield className="h-10 w-10 text-muted-foreground/40" />
            <p className="text-sm text-muted-foreground">No quality rules defined. Add rules and run a check.</p>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={runProfile} disabled={profiling}>Profile Data</Button>
              <Button variant="outline" size="sm" onClick={() => setAddOpen(true)}>
                <Plus className="h-3.5 w-3.5 mr-1" />Add Rule
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Add Rule Dialog */}
      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader><DialogTitle>Add Quality Rule</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div><Label className="text-sm">Rule Name</Label><Input value={ruleName} onChange={e => setRuleName(e.target.value)} placeholder="amount is not null" className="h-9" /></div>
            <div><Label className="text-sm">Check Type</Label>
              <Select value={checkType} onValueChange={setCheckType}>
                <SelectTrigger className="h-9"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="NOT_NULL">NOT_NULL</SelectItem>
                  <SelectItem value="UNIQUE">UNIQUE</SelectItem>
                  <SelectItem value="MIN_VALUE">MIN_VALUE</SelectItem>
                  <SelectItem value="MAX_VALUE">MAX_VALUE</SelectItem>
                  <SelectItem value="ROW_COUNT">ROW_COUNT</SelectItem>
                  <SelectItem value="FRESHNESS">FRESHNESS</SelectItem>
                  <SelectItem value="ACCEPTED_VALUES">ACCEPTED_VALUES</SelectItem>
                  <SelectItem value="REGEX">REGEX</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div><Label className="text-sm">Column (optional)</Label><Input value={columnName} onChange={e => setColumnName(e.target.value)} placeholder="amount" className="h-9" /></div>
            <div><Label className="text-sm">Expected Value</Label><Input value={expectedValue} onChange={e => setExpectedValue(e.target.value)} placeholder="0 or [&quot;A&quot;,&quot;B&quot;]" className="h-9" /></div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label className="text-sm">Threshold (%)</Label><Input type="number" value={threshold} onChange={e => setThreshold(e.target.value)} className="h-9" /></div>
              <div><Label className="text-sm">Severity</Label>
                <Select value={severity} onValueChange={setSeverity}>
                  <SelectTrigger className="h-9"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="BREAKING">BREAKING</SelectItem>
                    <SelectItem value="WARNING">WARNING</SelectItem>
                    <SelectItem value="INFO">INFO</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="flex justify-end"><Button onClick={addRule} disabled={!ruleName.trim()}>Add Rule</Button></div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}

function SeverityBadge({ severity }: { severity: string }) {
  if (severity === "BREAKING") return <Badge className="bg-red-500 text-white text-sm px-2 py-0.5 border-0">Breaking</Badge>
  if (severity === "WARNING") return <Badge className="bg-amber-500 text-white text-sm px-2 py-0.5 border-0">Warning</Badge>
  return <Badge variant="outline" className="text-sm px-2 py-0.5">Info</Badge>
}
