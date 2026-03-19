"use client"

import { useCallback, useEffect, useState } from "react"
import { Eye, EyeOff, Loader2, Play, Save } from "lucide-react"

import { Button } from "@workspace/ui/components/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@workspace/ui/components/card"
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"

import {
  fetchArgusConfig,
  testDockerRegistry,
  updateArgusConfig,
} from "@/features/settings/api"

export function ArgusSettings() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [showPassword, setShowPassword] = useState(false)

  const [registryUrl, setRegistryUrl] = useState("")
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")

  const [statusMessage, setStatusMessage] = useState<{ type: "success" | "error"; text: string } | null>(null)
  const [testResult, setTestResult] = useState<{ type: "success" | "error"; text: string } | null>(null)

  const loadConfig = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const config = await fetchArgusConfig()
      setRegistryUrl(config.docker_registry_url ?? "http://10.1.0.50:30000")
      setUsername(config.docker_registry_username ?? "admin")
      setPassword(config.docker_registry_password ?? "Argus!insight2026")
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

  const urlTrimmed = registryUrl.trim()
  const usernameTrimmed = username.trim()
  const passwordTrimmed = password.trim()

  const canSave = urlTrimmed.length > 0

  async function handleSave() {
    setSaving(true)
    try {
      await updateArgusConfig({
        docker_registry_url: registryUrl,
        docker_registry_username: username,
        docker_registry_password: password,
      })
      showStatus("success", "Docker Registry settings saved successfully")
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
      // Build the v2 endpoint URL
      let baseUrl = urlTrimmed.replace(/\/+$/, "")
      const v2Url = `${baseUrl}/v2/`

      const headers: Record<string, string> = {}
      if (usernameTrimmed && passwordTrimmed) {
        headers["Authorization"] = `Basic ${btoa(`${usernameTrimmed}:${passwordTrimmed}`)}`
      }

      const res = await fetch(v2Url, { headers })

      if (res.ok) {
        setTestResult({ type: "success", text: "Docker Registry connection successful" })
      } else if (res.status === 401) {
        setTestResult({ type: "error", text: "Authentication failed. Please check your username and password." })
      } else {
        setTestResult({ type: "error", text: `Connection failed with status ${res.status}` })
      }
    } catch {
      // If direct fetch fails (e.g. CORS), fall back to server-side test
      try {
        const result = await testDockerRegistry(urlTrimmed, usernameTrimmed, passwordTrimmed)
        if (result.success) {
          setTestResult({ type: "success", text: result.message || "Docker Registry connection successful" })
        } else {
          setTestResult({ type: "error", text: result.message || "Connection failed" })
        }
      } catch (err) {
        setTestResult({ type: "error", text: err instanceof Error ? err.message : "Test failed" })
      }
    } finally {
      setTesting(false)
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

  return (
    <div className="space-y-6">
      {statusMessage && (
        <div
          className={`rounded-md px-4 py-2 text-sm ${
            statusMessage.type === "success"
              ? "bg-green-50 text-green-800 dark:bg-green-950 dark:text-green-200"
              : "bg-red-50 text-red-800 dark:bg-red-950 dark:text-red-200"
          }`}
        >
          {statusMessage.text}
        </div>
      )}

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Docker Registry</CardTitle>
              <CardDescription>
                Docker Registry connection settings
              </CardDescription>
            </div>
            <div className="flex gap-2">
              <Button size="sm" onClick={handleSave} disabled={saving || !canSave}>
                {saving ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-1.5" />
                ) : (
                  <Save className="h-4 w-4 mr-1.5" />
                )}
                Save
              </Button>
              <Button size="sm" variant="outline" onClick={handleTest} disabled={testing || !canSave}>
                {testing ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-1.5" />
                ) : (
                  <Play className="h-4 w-4 mr-1.5" />
                )}
                Test
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {testResult && (
            <div
              className={`mb-4 rounded-md px-4 py-2 text-sm ${
                testResult.type === "success"
                  ? "bg-green-50 text-green-800 dark:bg-green-950 dark:text-green-200"
                  : "bg-red-50 text-red-800 dark:bg-red-950 dark:text-red-200"
              }`}
            >
              {testResult.text}
            </div>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="docker-registry-url">
                Docker Registry URL <span className="text-destructive">*</span>
              </Label>
              <Input
                id="docker-registry-url"
                value={registryUrl}
                onChange={(e) => setRegistryUrl(e.target.value)}
                placeholder="e.g. https://registry.example.com"
              />
              <p className="text-xs text-muted-foreground">
                Docker Registry server URL
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="docker-registry-username">Username</Label>
              <Input
                id="docker-registry-username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Registry username"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="docker-registry-password">Password</Label>
              <div className="relative">
                <Input
                  id="docker-registry-password"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Registry password"
                  className="pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((prev) => !prev)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                  tabIndex={-1}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </button>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
