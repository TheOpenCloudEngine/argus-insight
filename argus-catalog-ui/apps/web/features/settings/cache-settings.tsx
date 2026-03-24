"use client"

import { useCallback, useEffect, useState } from "react"
import { Loader2, Save, Trash2 } from "lucide-react"

import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@workspace/ui/components/card"
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"
import { Switch } from "@workspace/ui/components/switch"

import { authFetch } from "@/features/auth/auth-fetch"

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------

interface CacheConfig {
  max_size: number
  ttl_seconds: number
  enabled: boolean
  current_size: number
}

interface CacheStats {
  size: number
  max_size: number
  ttl_seconds: number
  hits: number
  misses: number
  hit_rate: number
  total_requests: number
}

async function fetchCacheConfig(): Promise<CacheConfig> {
  const res = await authFetch("/api/v1/external/cache/config")
  if (!res.ok) throw new Error("Failed to load cache config")
  return res.json()
}

async function updateCacheConfig(data: { max_size: number; ttl_seconds: number; enabled: boolean }): Promise<CacheConfig> {
  const res = await authFetch("/api/v1/external/cache/config", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error("Failed to save cache config")
  return res.json()
}

async function fetchCacheStats(): Promise<CacheStats> {
  const res = await authFetch("/api/v1/external/cache/stats")
  if (!res.ok) throw new Error("Failed to load cache stats")
  return res.json()
}

async function clearCache(): Promise<{ cleared: number }> {
  const res = await authFetch("/api/v1/external/cache", { method: "DELETE" })
  if (!res.ok) throw new Error("Failed to clear cache")
  return res.json()
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CacheSettings() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [clearing, setClearing] = useState(false)
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null)

  const [enabled, setEnabled] = useState(true)
  const [maxSize, setMaxSize] = useState(1000)
  const [ttl, setTtl] = useState(300)

  const [stats, setStats] = useState<CacheStats | null>(null)

  const load = useCallback(async () => {
    try {
      setLoading(true)
      const [cfg, st] = await Promise.all([
        fetchCacheConfig(),
        fetchCacheStats().catch(() => null),
      ])
      setEnabled(cfg.enabled)
      setMaxSize(cfg.max_size)
      setTtl(cfg.ttl_seconds)
      setStats(st)
    } catch {
      setMessage({ type: "error", text: "Failed to load cache configuration" })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleSave = async () => {
    setSaving(true)
    setMessage(null)
    try {
      await updateCacheConfig({ max_size: maxSize, ttl_seconds: ttl, enabled })
      setMessage({ type: "success", text: "Cache configuration saved" })
      const st = await fetchCacheStats().catch(() => null)
      setStats(st)
    } catch (e) {
      setMessage({ type: "error", text: e instanceof Error ? e.message : "Save failed" })
    } finally {
      setSaving(false)
    }
  }

  const handleClear = async () => {
    if (!confirm("Clear all cached metadata? Subsequent requests will be slower until the cache is rebuilt.")) return
    setClearing(true)
    setMessage(null)
    try {
      const result = await clearCache()
      setMessage({ type: "success", text: `Cache cleared: ${result.cleared} entries removed` })
      const st = await fetchCacheStats().catch(() => null)
      setStats(st)
    } catch (e) {
      setMessage({ type: "error", text: e instanceof Error ? e.message : "Clear failed" })
    } finally {
      setClearing(false)
    }
  }

  if (loading) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center gap-2 text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading cache settings...
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      {/* Message */}
      {message && (
        <div className={`rounded-lg border px-4 py-3 text-sm ${
          message.type === "success"
            ? "border-green-200 bg-green-50 text-green-800"
            : "border-red-200 bg-red-50 text-red-800"
        }`}>
          {message.text}
        </div>
      )}

      {/* Configuration Card */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">External Metadata Cache</CardTitle>
          <CardDescription>
            외부 시스템용 메타데이터 API의 캐시 설정입니다. 캐시를 사용하면 반복 요청의 응답 시간이 대폭 향상됩니다.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Enabled toggle */}
          <div className="flex items-center justify-between">
            <div>
              <Label className="text-sm font-medium">Enable Cache</Label>
              <p className="text-xs text-muted-foreground">비활성화하면 모든 요청이 DB에서 직접 조회됩니다</p>
            </div>
            <Switch checked={enabled} onCheckedChange={setEnabled} />
          </div>

          {/* Max size */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="max-size" className="text-sm">Max Size (항목 수)</Label>
              <Input
                id="max-size"
                type="number"
                min={10}
                max={100000}
                value={maxSize}
                onChange={(e) => setMaxSize(Number(e.target.value))}
                className="h-9"
              />
              <p className="text-xs text-muted-foreground">
                최대 캐시 항목 수. 초과 시 가장 오래된 항목이 LRU 방식으로 제거됩니다.
              </p>
            </div>

            {/* TTL */}
            <div className="space-y-2">
              <Label htmlFor="ttl" className="text-sm">TTL (초)</Label>
              <Input
                id="ttl"
                type="number"
                min={10}
                max={86400}
                value={ttl}
                onChange={(e) => setTtl(Number(e.target.value))}
                className="h-9"
              />
              <p className="text-xs text-muted-foreground">
                캐시 항목 만료 시간. {ttl >= 60 ? `${Math.floor(ttl / 60)}분` : `${ttl}초`} 후 자동 갱신됩니다.
              </p>
            </div>
          </div>

          {/* Save button */}
          <div className="flex gap-2 pt-2">
            <Button onClick={handleSave} disabled={saving} size="sm">
              {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
              Save
            </Button>
            <Button onClick={handleClear} disabled={clearing} variant="outline" size="sm">
              {clearing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Trash2 className="mr-2 h-4 w-4" />}
              Clear Cache
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Statistics Card */}
      {stats && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Cache Statistics</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StatItem label="Current Size" value={`${stats.size} / ${stats.max_size}`} />
              <StatItem label="Hit Rate" value={`${stats.hit_rate}%`} highlight={stats.hit_rate >= 80} />
              <StatItem label="Hits" value={stats.hits.toLocaleString()} />
              <StatItem label="Misses" value={stats.misses.toLocaleString()} />
            </div>
            <div className="mt-3 text-xs text-muted-foreground">
              Total requests: {stats.total_requests.toLocaleString()} · TTL: {stats.ttl_seconds}s
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

function StatItem({ label, value, highlight }: { label: string; value: string | number; highlight?: boolean }) {
  return (
    <div className="text-center">
      <div className="text-xs text-muted-foreground mb-1">{label}</div>
      <div className={`text-lg font-semibold ${highlight ? "text-green-600" : ""}`}>{value}</div>
    </div>
  )
}
