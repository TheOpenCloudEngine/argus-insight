"use client"

import { useCallback, useEffect, useState } from "react"
import { Check, CheckCircle2, Eye, EyeOff, Loader2, Play, Rocket, Save, SkipForward, X, XCircle } from "lucide-react"

import { Button } from "@workspace/ui/components/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@workspace/ui/components/card"
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@workspace/ui/components/dialog"
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@workspace/ui/components/select"

import {
  fetchObjectStorageConfig,
  initializeObjectStorage,
  testObjectStorage,
  updateObjectStorageConfig,
  type InitStep,
} from "./api"

function StepIcon({ status }: { status: string }) {
  if (status === "ok") return <CheckCircle2 className="h-4 w-4 text-blue-500" />
  if (status === "created") return <CheckCircle2 className="h-4 w-4 text-emerald-500" />
  if (status === "skip") return <SkipForward className="h-4 w-4 text-muted-foreground" />
  return <XCircle className="h-4 w-4 text-red-500" />
}

function StepBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    ok: "bg-blue-50 text-blue-700 border-blue-200",
    created: "bg-emerald-50 text-emerald-700 border-emerald-200",
    skip: "bg-muted text-muted-foreground border-muted",
    error: "bg-red-50 text-red-700 border-red-200",
  }
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold ${colors[status] || colors.error}`}>
      {status.toUpperCase()}
    </span>
  )
}

export function OciModelRegistrySettings() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [endpoint, setEndpoint] = useState("")
  const [accessKey, setAccessKey] = useState("")
  const [secretKey, setSecretKey] = useState("")
  const [region, setRegion] = useState("us-east-1")
  const [useSsl, setUseSsl] = useState("false")
  const [bucket, setBucket] = useState("model-artifacts")
  const [presignedUrlExpiry, setPresignedUrlExpiry] = useState("3600")

  const [showSecretKey, setShowSecretKey] = useState(false)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [statusMessage, setStatusMessage] = useState<{ type: "success" | "error"; text: string } | null>(null)
  const [testResult, setTestResult] = useState<{ type: "success" | "error"; text: string } | null>(null)

  // Initialize dialog
  const [initOpen, setInitOpen] = useState(false)
  const [initRunning, setInitRunning] = useState(false)
  const [initSteps, setInitSteps] = useState<InitStep[]>([])

  const loadConfig = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const config = await fetchObjectStorageConfig()
      setEndpoint(config.endpoint)
      setAccessKey(config.access_key)
      setSecretKey(config.secret_key)
      setRegion(config.region)
      setUseSsl(config.use_ssl ? "true" : "false")
      setBucket(config.bucket)
      setPresignedUrlExpiry(String(config.presigned_url_expiry))
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load configuration")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadConfig()
  }, [loadConfig])

  function showStatus(type: "success" | "error", text: string) {
    setStatusMessage({ type, text })
    setTimeout(() => setStatusMessage(null), 3000)
  }

  const canSave = endpoint.trim().length > 0

  async function handleSave() {
    setSaving(true)
    try {
      await updateObjectStorageConfig({
        endpoint,
        access_key: accessKey,
        secret_key: secretKey,
        region,
        use_ssl: useSsl === "true",
        bucket,
        presigned_url_expiry: parseInt(presignedUrlExpiry) || 3600,
      })
      showStatus("success", "Object Storage settings saved successfully")
      await loadConfig()
    } catch (err) {
      showStatus("error", err instanceof Error ? err.message : "Failed to save")
    } finally {
      setSaving(false)
    }
  }

  async function handleTest() {
    setTesting(true)
    setTestResult(null)
    try {
      const result = await testObjectStorage(endpoint.trim(), accessKey.trim(), secretKey.trim(), region.trim(), bucket.trim())
      setTestResult({
        type: result.success ? "success" : "error",
        text: result.message,
      })
    } catch (err) {
      setTestResult({ type: "error", text: err instanceof Error ? err.message : "Test failed" })
    } finally {
      setTesting(false)
    }
  }

  function handleOpenInit() {
    const missing: string[] = []
    if (!endpoint.trim()) missing.push("Endpoint")
    if (!accessKey.trim()) missing.push("Access Key")
    if (!secretKey.trim()) missing.push("Secret Key")
    if (!bucket.trim()) missing.push("Bucket")
    if (missing.length > 0) {
      showStatus("error", `Required fields missing: ${missing.join(", ")}`)
      return
    }
    setInitSteps([])
    setInitOpen(true)
  }

  async function handleInitialize() {
    setInitRunning(true)
    setInitSteps([])
    try {
      const result = await initializeObjectStorage(
        endpoint.trim(), accessKey.trim(), secretKey.trim(), region.trim(), bucket.trim(),
      )
      setInitSteps(result.steps)
    } catch (e) {
      setInitSteps([{ step: "Initialize", status: "error", message: e instanceof Error ? e.message : "Failed" }])
    } finally {
      setInitRunning(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        <span className="ml-2 text-sm text-muted-foreground">Loading configuration...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-12 gap-3">
        <p className="text-sm text-destructive">{error}</p>
        <Button variant="outline" size="sm" onClick={loadConfig}>
          Retry
        </Button>
      </div>
    )
  }

  const hasErrors = initSteps.some((s) => s.status === "error")
  const createdCount = initSteps.filter((s) => s.status === "created").length

  return (
    <div className="space-y-6">
      {statusMessage && (
        <div
          className={`flex items-center gap-2 rounded-md px-4 py-2 text-sm ${
            statusMessage.type === "success"
              ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
              : "bg-red-50 text-red-700 border border-red-200"
          }`}
        >
          {statusMessage.type === "success" ? <Check className="h-4 w-4" /> : <X className="h-4 w-4" />}
          {statusMessage.text}
        </div>
      )}

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Object Storage (MinIO / S3)</CardTitle>
              <CardDescription>
                S3-compatible Object Storage connection settings for the OCI Model Registry
              </CardDescription>
            </div>
            <div className="flex gap-2">
              <Button size="sm" onClick={handleSave} disabled={saving || !canSave}>
                {saving ? <Loader2 className="h-4 w-4 animate-spin mr-1.5" /> : <Save className="h-4 w-4 mr-1.5" />}
                Save
              </Button>
              <Button size="sm" variant="outline" onClick={handleTest} disabled={testing || !canSave}>
                {testing ? <Loader2 className="h-4 w-4 animate-spin mr-1.5" /> : <Play className="h-4 w-4 mr-1.5" />}
                Test
              </Button>
              <Button size="sm" variant="outline" onClick={handleOpenInit}>
                <Rocket className="h-4 w-4 mr-1.5" />
                Initialize
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {testResult && (
            <div
              className={`mb-4 flex items-center gap-2 rounded-md px-4 py-2 text-sm ${
                testResult.type === "success"
                  ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                  : "bg-red-50 text-red-700 border border-red-200"
              }`}
            >
              {testResult.type === "success" ? <Check className="h-4 w-4" /> : <X className="h-4 w-4" />}
              {testResult.text}
            </div>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="os-endpoint">
                Endpoint <span className="text-destructive">*</span>
              </Label>
              <Input
                id="os-endpoint"
                value={endpoint}
                onChange={(e) => setEndpoint(e.target.value)}
                placeholder="e.g. http://10.0.1.50:51000"
              />
              <p className="text-xs text-muted-foreground">
                S3-compatible Object Storage endpoint URL (MinIO, AWS S3, etc.)
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="os-access-key">Access Key</Label>
              <Input
                id="os-access-key"
                value={accessKey}
                onChange={(e) => setAccessKey(e.target.value)}
                placeholder="Access Key"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="os-secret-key">Secret Key</Label>
              <div className="relative">
                <Input
                  id="os-secret-key"
                  type={showSecretKey ? "text" : "password"}
                  value={secretKey}
                  onChange={(e) => setSecretKey(e.target.value)}
                  placeholder="Secret Key"
                  className="pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowSecretKey((prev) => !prev)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                  tabIndex={-1}
                >
                  {showSecretKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="os-region">Region</Label>
              <Input
                id="os-region"
                value={region}
                onChange={(e) => setRegion(e.target.value)}
                placeholder="us-east-1"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="os-use-ssl">Use SSL</Label>
              <Select value={useSsl} onValueChange={setUseSsl}>
                <SelectTrigger id="os-use-ssl">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="true">true</SelectItem>
                  <SelectItem value="false">false</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="os-bucket">Bucket</Label>
              <Input
                id="os-bucket"
                value={bucket}
                onChange={(e) => setBucket(e.target.value)}
                placeholder="model-artifacts"
              />
              <p className="text-xs text-muted-foreground">
                S3 bucket for model artifacts storage
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="os-presigned-url-expiry">Presigned URL Expiry</Label>
              <Input
                id="os-presigned-url-expiry"
                value={presignedUrlExpiry}
                onChange={(e) => setPresignedUrlExpiry(e.target.value)}
                placeholder="3600"
              />
              <p className="text-xs text-muted-foreground">
                Presigned URL expiry in seconds (default: 3600)
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Initialize Dialog */}
      <Dialog open={initOpen} onOpenChange={(open) => { if (!initRunning) setInitOpen(open) }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Rocket className="h-5 w-5" />
              Initialize Object Storage
            </DialogTitle>
            <DialogDescription>
              Check if the bucket exists and create it if necessary.
            </DialogDescription>
          </DialogHeader>

          {initSteps.length === 0 && !initRunning && (
            <div className="py-2 text-sm text-muted-foreground">
              <p>This will connect to <strong>{endpoint}</strong> and ensure the bucket <strong>{bucket}</strong> exists.</p>
            </div>
          )}

          {initSteps.length > 0 && (
            <div className="space-y-2 py-2">
              {initSteps.map((s, i) => (
                <div key={i} className="flex items-start gap-2 text-sm">
                  <StepIcon status={s.status} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{s.step}</span>
                      <StepBadge status={s.status} />
                    </div>
                    <p className="text-xs text-muted-foreground">{s.message}</p>
                  </div>
                </div>
              ))}

              {!initRunning && (
                <div className={`mt-3 rounded-md px-3 py-2 text-sm ${
                  hasErrors
                    ? "bg-red-50 text-red-700 border border-red-200"
                    : "bg-emerald-50 text-emerald-700 border border-emerald-200"
                }`}>
                  {hasErrors
                    ? "Initialization completed with errors."
                    : createdCount > 0
                      ? `Initialization complete. Bucket '${bucket}' is ready.`
                      : `Bucket '${bucket}' already exists. Nothing to do.`
                  }
                </div>
              )}
            </div>
          )}

          {initRunning && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground py-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              Initializing...
            </div>
          )}

          <DialogFooter>
            {initSteps.length === 0 && !initRunning ? (
              <>
                <Button variant="outline" onClick={() => setInitOpen(false)}>Cancel</Button>
                <Button onClick={handleInitialize}>
                  <Rocket className="h-4 w-4 mr-1" />
                  Start
                </Button>
              </>
            ) : (
              <Button onClick={() => { setInitOpen(false); setInitSteps([]) }}>
                Close
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
