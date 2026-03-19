"use client"

import { useCallback, useEffect, useState } from "react"
import { Eye, EyeOff, Loader2, Play, Rocket, Save } from "lucide-react"

import { Button } from "@workspace/ui/components/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@workspace/ui/components/card"
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"

import {
  fetchArgusConfig,
  initializeUnityCatalog,
  testDockerRegistry,
  testObjectStorage,
  testUnityCatalog,
  updateArgusConfig,
} from "@/features/settings/api"

export function ArgusSettings() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [showPassword, setShowPassword] = useState(false)

  const [osEndpoint, setOsEndpoint] = useState("")
  const [osAccessKey, setOsAccessKey] = useState("")
  const [osSecretKey, setOsSecretKey] = useState("")
  const [osRegion, setOsRegion] = useState("us-east-1")
  const [osSaving, setOsSaving] = useState(false)
  const [osTesting, setOsTesting] = useState(false)
  const [showOsSecretKey, setShowOsSecretKey] = useState(false)
  const [osStatusMessage, setOsStatusMessage] = useState<{ type: "success" | "error"; text: string } | null>(null)
  const [osTestResult, setOsTestResult] = useState<{ type: "success" | "error"; text: string } | null>(null)

  const [registryUrl, setRegistryUrl] = useState("")
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")

  const [ucUrl, setUcUrl] = useState("")
  const [ucAccessToken, setUcAccessToken] = useState("")
  const [ucSaving, setUcSaving] = useState(false)
  const [ucTesting, setUcTesting] = useState(false)
  const [ucInitializing, setUcInitializing] = useState(false)
  const [showUcToken, setShowUcToken] = useState(false)

  const [statusMessage, setStatusMessage] = useState<{ type: "success" | "error"; text: string } | null>(null)
  const [testResult, setTestResult] = useState<{ type: "success" | "error"; text: string } | null>(null)
  const [ucStatusMessage, setUcStatusMessage] = useState<{ type: "success" | "error"; text: string } | null>(null)
  const [ucTestResult, setUcTestResult] = useState<{ type: "success" | "error"; text: string } | null>(null)

  const loadConfig = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const config = await fetchArgusConfig()
      setOsEndpoint(config.object_storage_endpoint ?? "")
      setOsAccessKey(config.object_storage_access_key ?? "")
      setOsSecretKey(config.object_storage_secret_key ?? "")
      setOsRegion(config.object_storage_region ?? "us-east-1")
      setRegistryUrl(config.docker_registry_url ?? "https://zot.argus-insight.dev.net:30000")
      setUsername(config.docker_registry_username ?? "admin")
      setPassword(config.docker_registry_password ?? "Argus!insight2026")
      setUcUrl(config.unity_catalog_url ?? "")
      setUcAccessToken(config.unity_catalog_access_token ?? "")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load configuration")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadConfig()
  }, [loadConfig])

  // -- Object Storage handlers --

  const osEndpointTrimmed = osEndpoint.trim()
  const canSaveOs = osEndpointTrimmed.length > 0

  function showOsStatus(type: "success" | "error", text: string) {
    setOsStatusMessage({ type, text })
    setTimeout(() => setOsStatusMessage(null), 3000)
  }

  async function handleOsSave() {
    setOsSaving(true)
    try {
      await updateArgusConfig({
        object_storage_endpoint: osEndpoint,
        object_storage_access_key: osAccessKey,
        object_storage_secret_key: osSecretKey,
        object_storage_region: osRegion,
      })
      showOsStatus("success", "Object Storage settings saved successfully")
      await loadConfig()
    } catch (err) {
      showOsStatus("error", err instanceof Error ? err.message : "Failed to save")
    } finally {
      setOsSaving(false)
    }
  }

  async function handleOsTest() {
    setOsTesting(true)
    setOsTestResult(null)
    try {
      const result = await testObjectStorage(osEndpointTrimmed, osAccessKey.trim(), osSecretKey.trim(), osRegion.trim())
      if (result.success) {
        setOsTestResult({ type: "success", text: result.message || "Object Storage connection successful" })
      } else {
        setOsTestResult({ type: "error", text: result.message || "Connection failed" })
      }
    } catch (err) {
      setOsTestResult({ type: "error", text: err instanceof Error ? err.message : "Test failed" })
    } finally {
      setOsTesting(false)
    }
  }

  // -- Docker Registry handlers --

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
      showStatus("success", "Zot Docker Registry settings saved successfully")
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
      const result = await testDockerRegistry(urlTrimmed, usernameTrimmed, passwordTrimmed)
      if (result.success) {
        setTestResult({ type: "success", text: result.message || "Zot Docker Registry connection successful" })
      } else {
        setTestResult({ type: "error", text: result.message || "Connection failed" })
      }
    } catch (err) {
      setTestResult({ type: "error", text: err instanceof Error ? err.message : "Test failed" })
    } finally {
      setTesting(false)
    }
  }

  const ucUrlTrimmed = ucUrl.trim()
  const ucAccessTokenTrimmed = ucAccessToken.trim()
  const canSaveUc = ucUrlTrimmed.length > 0

  function showUcStatus(type: "success" | "error", text: string) {
    setUcStatusMessage({ type, text })
    setTimeout(() => setUcStatusMessage(null), 3000)
  }

  async function handleUcSave() {
    setUcSaving(true)
    try {
      await updateArgusConfig({
        unity_catalog_url: ucUrl,
        unity_catalog_access_token: ucAccessToken,
      })
      showUcStatus("success", "Unity Catalog settings saved successfully")
      await loadConfig()
    } catch (err) {
      showUcStatus("error", err instanceof Error ? err.message : "Failed to save")
    } finally {
      setUcSaving(false)
    }
  }

  async function handleUcTest() {
    setUcTesting(true)
    setUcTestResult(null)
    try {
      const result = await testUnityCatalog(ucUrlTrimmed, ucAccessTokenTrimmed)
      if (result.success) {
        setUcTestResult({ type: "success", text: result.message || "Unity Catalog connection successful" })
      } else {
        setUcTestResult({ type: "error", text: result.message || "Connection failed" })
      }
    } catch (err) {
      setUcTestResult({ type: "error", text: err instanceof Error ? err.message : "Test failed" })
    } finally {
      setUcTesting(false)
    }
  }

  async function handleUcInitialize() {
    setUcInitializing(true)
    setUcTestResult(null)
    try {
      const result = await initializeUnityCatalog(ucUrlTrimmed, ucAccessTokenTrimmed)
      if (result.success) {
        setUcTestResult({ type: "success", text: result.message || "Unity Catalog initialized successfully" })
      } else {
        setUcTestResult({ type: "error", text: result.message || "Initialization failed" })
      }
    } catch (err) {
      setUcTestResult({ type: "error", text: err instanceof Error ? err.message : "Initialization failed" })
    } finally {
      setUcInitializing(false)
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
      {osStatusMessage && (
        <div
          className={`rounded-md px-4 py-2 text-sm ${
            osStatusMessage.type === "success"
              ? "bg-green-50 text-green-800 dark:bg-green-950 dark:text-green-200"
              : "bg-red-50 text-red-800 dark:bg-red-950 dark:text-red-200"
          }`}
        >
          {osStatusMessage.text}
        </div>
      )}

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Object Storage</CardTitle>
              <CardDescription>
                S3-compatible Object Storage connection settings
              </CardDescription>
            </div>
            <div className="flex gap-2">
              <Button size="sm" onClick={handleOsSave} disabled={osSaving || !canSaveOs}>
                {osSaving ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-1.5" />
                ) : (
                  <Save className="h-4 w-4 mr-1.5" />
                )}
                Save
              </Button>
              <Button size="sm" variant="outline" onClick={handleOsTest} disabled={osTesting || !canSaveOs}>
                {osTesting ? (
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
          {osTestResult && (
            <div
              className={`mb-4 rounded-md px-4 py-2 text-sm ${
                osTestResult.type === "success"
                  ? "bg-green-50 text-green-800 dark:bg-green-950 dark:text-green-200"
                  : "bg-red-50 text-red-800 dark:bg-red-950 dark:text-red-200"
              }`}
            >
              {osTestResult.text}
            </div>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="os-endpoint">
                Endpoint <span className="text-destructive">*</span>
              </Label>
              <Input
                id="os-endpoint"
                value={osEndpoint}
                onChange={(e) => setOsEndpoint(e.target.value)}
                placeholder="e.g. https://s3.amazonaws.com"
              />
              <p className="text-xs text-muted-foreground">
                S3-compatible Object Storage endpoint URL
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="os-access-key">Access Key</Label>
              <Input
                id="os-access-key"
                value={osAccessKey}
                onChange={(e) => setOsAccessKey(e.target.value)}
                placeholder="Access Key"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="os-secret-key">Secret Key</Label>
              <div className="relative">
                <Input
                  id="os-secret-key"
                  type={showOsSecretKey ? "text" : "password"}
                  value={osSecretKey}
                  onChange={(e) => setOsSecretKey(e.target.value)}
                  placeholder="Secret Key"
                  className="pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowOsSecretKey((prev) => !prev)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                  tabIndex={-1}
                  aria-label={showOsSecretKey ? "Hide secret key" : "Show secret key"}
                >
                  {showOsSecretKey ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </button>
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="os-region">Region</Label>
              <Input
                id="os-region"
                value={osRegion}
                onChange={(e) => setOsRegion(e.target.value)}
                placeholder="us-east-1"
              />
            </div>
          </div>
        </CardContent>
      </Card>

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
              <CardTitle>Zot Docker Registry</CardTitle>
              <CardDescription>
                Zot Docker Registry connection settings
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
                Zot Docker Registry URL <span className="text-destructive">*</span>
              </Label>
              <Input
                id="docker-registry-url"
                value={registryUrl}
                onChange={(e) => setRegistryUrl(e.target.value)}
                placeholder="e.g. https://registry.example.com"
              />
              <p className="text-xs text-muted-foreground">
                Zot Docker Registry server URL
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

      {ucStatusMessage && (
        <div
          className={`rounded-md px-4 py-2 text-sm ${
            ucStatusMessage.type === "success"
              ? "bg-green-50 text-green-800 dark:bg-green-950 dark:text-green-200"
              : "bg-red-50 text-red-800 dark:bg-red-950 dark:text-red-200"
          }`}
        >
          {ucStatusMessage.text}
        </div>
      )}

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Unity Catalog</CardTitle>
              <CardDescription>
                Unity Catalog connection settings
              </CardDescription>
            </div>
            <div className="flex gap-2">
              <Button size="sm" onClick={handleUcSave} disabled={ucSaving || !canSaveUc}>
                {ucSaving ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-1.5" />
                ) : (
                  <Save className="h-4 w-4 mr-1.5" />
                )}
                Save
              </Button>
              <Button size="sm" variant="outline" onClick={handleUcTest} disabled={ucTesting || !canSaveUc}>
                {ucTesting ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-1.5" />
                ) : (
                  <Play className="h-4 w-4 mr-1.5" />
                )}
                Test
              </Button>
              <Button size="sm" variant="outline" onClick={handleUcInitialize} disabled={ucInitializing || !canSaveUc}>
                {ucInitializing ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-1.5" />
                ) : (
                  <Rocket className="h-4 w-4 mr-1.5" />
                )}
                Initialize
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {ucTestResult && (
            <div
              className={`mb-4 rounded-md px-4 py-2 text-sm ${
                ucTestResult.type === "success"
                  ? "bg-green-50 text-green-800 dark:bg-green-950 dark:text-green-200"
                  : "bg-red-50 text-red-800 dark:bg-red-950 dark:text-red-200"
              }`}
            >
              {ucTestResult.text}
            </div>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="unity-catalog-url">
                Unity Catalog URL <span className="text-destructive">*</span>
              </Label>
              <Input
                id="unity-catalog-url"
                value={ucUrl}
                onChange={(e) => setUcUrl(e.target.value)}
                placeholder="e.g. https://unity-catalog.example.com"
              />
              <p className="text-xs text-muted-foreground">
                Unity Catalog server URL
              </p>
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="unity-catalog-access-token">Access Token</Label>
              <div className="relative">
                <Input
                  id="unity-catalog-access-token"
                  type={showUcToken ? "text" : "password"}
                  value={ucAccessToken}
                  onChange={(e) => setUcAccessToken(e.target.value)}
                  placeholder="Unity Catalog access token"
                  className="pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowUcToken((prev) => !prev)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                  tabIndex={-1}
                  aria-label={showUcToken ? "Hide token" : "Show token"}
                >
                  {showUcToken ? (
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
