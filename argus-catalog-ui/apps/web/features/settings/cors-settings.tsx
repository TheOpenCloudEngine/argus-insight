"use client"

import { useCallback, useEffect, useState } from "react"
import { Check, Loader2, Save, X } from "lucide-react"

import { Button } from "@workspace/ui/components/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@workspace/ui/components/card"
import { Label } from "@workspace/ui/components/label"
import { Textarea } from "@workspace/ui/components/textarea"

import { fetchCorsConfig, updateCorsConfig } from "./api"

export function CorsSettings() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null)
  const [origins, setOrigins] = useState("*")

  const loadConfig = useCallback(async () => {
    try {
      setLoading(true)
      const cfg = await fetchCorsConfig()
      setOrigins(cfg.origins)
    } catch {
      setMessage({ type: "error", text: "Failed to load CORS configuration" })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadConfig() }, [loadConfig])

  const handleSave = async () => {
    setSaving(true)
    setMessage(null)
    try {
      await updateCorsConfig({ origins })
      setMessage({ type: "success", text: "CORS configuration saved. Changes take effect on next request." })
    } catch (e) {
      setMessage({ type: "error", text: e instanceof Error ? e.message : "Save failed" })
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return <div className="flex items-center justify-center py-12"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>
  }

  return (
    <div className="space-y-4 max-w-2xl">
      {message && (
        <div className={`flex items-center gap-2 rounded-md px-3 py-2 text-sm ${
          message.type === "success" ? "bg-emerald-50 text-emerald-700 border border-emerald-200" : "bg-red-50 text-red-700 border border-red-200"
        }`}>
          {message.type === "success" ? <Check className="h-4 w-4" /> : <X className="h-4 w-4" />}
          {message.text}
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">CORS Origins</CardTitle>
          <CardDescription>
            Configure which origins are allowed to make cross-origin requests to the API.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <Label>Allowed Origins</Label>
            <Textarea
              value={origins}
              onChange={(e) => setOrigins(e.target.value)}
              placeholder="http://localhost:3000, https://catalog.example.com"
              rows={3}
            />
            <p className="text-xs text-muted-foreground">
              Comma-separated list of allowed origins. Use <code className="bg-muted px-1 rounded">*</code> to allow all origins (not recommended for production).
            </p>
          </div>

          <Button onClick={handleSave} disabled={saving}>
            {saving ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Save className="h-4 w-4 mr-1" />}
            Save
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
