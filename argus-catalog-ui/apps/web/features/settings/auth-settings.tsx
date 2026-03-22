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

import {
  fetchAuthConfig, fetchAuthSecret, initializeKeycloak,
  testAuthConnection, updateAuthConfig,
  type AuthConfig, type InitStep,
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

export function AuthSettings() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null)

  const [serverUrl, setServerUrl] = useState("")
  const [realm, setRealm] = useState("")
  const [clientId, setClientId] = useState("")
  const [clientSecret, setClientSecret] = useState("")
  const [adminRole, setAdminRole] = useState("")
  const [superuserRole, setSuperuserRole] = useState("")
  const [userRole, setUserRole] = useState("")
  const [showSecret, setShowSecret] = useState(false)
  const [realSecret, setRealSecret] = useState<string | null>(null)

  // Initialize dialog
  const [initOpen, setInitOpen] = useState(false)
  const [initRunning, setInitRunning] = useState(false)
  const [initSteps, setInitSteps] = useState<InitStep[]>([])
  const [initAdminUser, setInitAdminUser] = useState("admin")
  const [initAdminPass, setInitAdminPass] = useState("admin")

  const handleToggleSecret = async () => {
    if (!showSecret && realSecret === null) {
      try {
        const secret = await fetchAuthSecret()
        setRealSecret(secret)
        setClientSecret(secret)
      } catch {
        // ignore
      }
    }
    setShowSecret(!showSecret)
  }

  const loadConfig = useCallback(async () => {
    try {
      setLoading(true)
      const cfg = await fetchAuthConfig()
      setServerUrl(cfg.server_url)
      setRealm(cfg.realm)
      setClientId(cfg.client_id)
      setClientSecret(cfg.client_secret)
      setAdminRole(cfg.admin_role)
      setSuperuserRole(cfg.superuser_role)
      setUserRole(cfg.user_role)
    } catch {
      setMessage({ type: "error", text: "Failed to load authentication configuration" })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadConfig() }, [loadConfig])

  const handleSave = async () => {
    setSaving(true)
    setMessage(null)
    try {
      await updateAuthConfig({
        type: "keycloak",
        server_url: serverUrl, realm, client_id: clientId, client_secret: clientSecret,
        admin_role: adminRole, superuser_role: superuserRole, user_role: userRole,
      })
      setMessage({ type: "success", text: "Authentication configuration saved" })
    } catch (e) {
      setMessage({ type: "error", text: e instanceof Error ? e.message : "Save failed" })
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async () => {
    setTesting(true)
    setMessage(null)
    try {
      const result = await testAuthConnection({
        type: "keycloak",
        server_url: serverUrl, realm, client_id: clientId, client_secret: clientSecret,
        admin_role: adminRole, superuser_role: superuserRole, user_role: userRole,
      })
      setMessage({ type: result.success ? "success" : "error", text: result.message })
    } catch (e) {
      setMessage({ type: "error", text: e instanceof Error ? e.message : "Test failed" })
    } finally {
      setTesting(false)
    }
  }

  const handleOpenInit = () => {
    // Validate all required fields before opening the dialog
    const missing: string[] = []
    if (!serverUrl.trim()) missing.push("Server URL")
    if (!initAdminUser.trim()) missing.push("Admin Username")
    if (!initAdminPass.trim()) missing.push("Admin Password")
    if (!realm.trim()) missing.push("Realm")
    if (!clientId.trim()) missing.push("Client ID")
    if (!clientSecret.trim() || clientSecret === "••••••••" && !realSecret) {
      // Need to resolve masked secret
    }
    if (!adminRole.trim()) missing.push("Admin Role")
    if (!superuserRole.trim()) missing.push("Superuser Role")
    if (!userRole.trim()) missing.push("User Role")

    if (missing.length > 0) {
      setMessage({ type: "error", text: `Required fields missing: ${missing.join(", ")}` })
      return
    }
    setMessage(null)
    setInitSteps([])
    setInitOpen(true)
  }

  const handleInitialize = async () => {
    setInitRunning(true)
    setInitSteps([])
    try {
      // Get real secret if masked
      let secret = clientSecret
      if (secret === "••••••••" && realSecret) {
        secret = realSecret
      } else if (secret === "••••••••") {
        try {
          secret = await fetchAuthSecret()
        } catch {
          secret = "argus-client-secret"
        }
      }

      const result = await initializeKeycloak({
        server_url: serverUrl,
        admin_username: initAdminUser,
        admin_password: initAdminPass,
        realm,
        client_id: clientId,
        client_secret: secret,
        roles: [adminRole, superuserRole, userRole].filter(Boolean),
      })
      setInitSteps(result.steps)
    } catch (e) {
      setInitSteps([{ step: "Initialize", status: "error", message: e instanceof Error ? e.message : "Failed" }])
    } finally {
      setInitRunning(false)
    }
  }

  if (loading) {
    return <div className="flex items-center justify-center py-12"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>
  }

  const hasErrors = initSteps.some((s) => s.status === "error")
  const createdCount = initSteps.filter((s) => s.status === "created").length

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
          <CardTitle className="text-base">Keycloak OIDC</CardTitle>
          <CardDescription>Configure Keycloak server connection for SSO authentication.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label>Server URL <span className="text-red-500">*</span></Label>
              <Input value={serverUrl} onChange={(e) => setServerUrl(e.target.value)} placeholder="http://localhost:8180" />
            </div>
            <div className="space-y-1.5">
              <Label>Realm <span className="text-red-500">*</span></Label>
              <Input value={realm} onChange={(e) => setRealm(e.target.value)} placeholder="argus" />
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label>Admin Username</Label>
              <Input value={initAdminUser} onChange={(e) => setInitAdminUser(e.target.value)} placeholder="admin" />
              <p className="text-xs text-muted-foreground">Keycloak admin account for Initialize.</p>
            </div>
            <div className="space-y-1.5">
              <Label>Admin Password</Label>
              <Input type="password" value={initAdminPass} onChange={(e) => setInitAdminPass(e.target.value)} placeholder="admin" />
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label>Client ID <span className="text-red-500">*</span></Label>
              <Input value={clientId} onChange={(e) => setClientId(e.target.value)} placeholder="argus-client" />
            </div>
            <div className="space-y-1.5">
              <Label>Client Secret <span className="text-red-500">*</span></Label>
              <div className="relative">
                <Input
                  type={showSecret ? "text" : "password"}
                  value={clientSecret}
                  onChange={(e) => setClientSecret(e.target.value)}
                  placeholder="••••••••"
                  className="pr-10"
                />
                <button
                  type="button"
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground"
                  onClick={handleToggleSecret}
                >
                  {showSecret ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              <p className="text-xs text-muted-foreground">Leave unchanged to keep existing secret.</p>
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <div className="space-y-1.5">
              <Label>Admin Role</Label>
              <Input value={adminRole} readOnly className="bg-muted" />
            </div>
            <div className="space-y-1.5">
              <Label>Superuser Role</Label>
              <Input value={superuserRole} readOnly className="bg-muted" />
            </div>
            <div className="space-y-1.5">
              <Label>User Role</Label>
              <Input value={userRole} readOnly className="bg-muted" />
            </div>
          </div>

          <div className="flex items-center gap-2 pt-2">
            <Button onClick={handleSave} disabled={saving}>
              {saving ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Save className="h-4 w-4 mr-1" />}
              Save
            </Button>
            <Button variant="outline" onClick={handleTest} disabled={testing}>
              {testing ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Play className="h-4 w-4 mr-1" />}
              Test Connection
            </Button>
            <Button variant="outline" onClick={handleOpenInit}>
              <Rocket className="h-4 w-4 mr-1" />
              Initialize
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Initialize Dialog */}
      <Dialog open={initOpen} onOpenChange={(open) => { if (!initRunning) setInitOpen(open) }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Rocket className="h-5 w-5" />
              Initialize Keycloak
            </DialogTitle>
            <DialogDescription>
              Automatically create the realm, client, and roles in Keycloak.
              Existing resources will be skipped.
            </DialogDescription>
          </DialogHeader>

          {initSteps.length === 0 && (
            <div className="py-2">
              <p className="text-sm text-muted-foreground">
                Uses the Admin Username and Password configured above to access the Keycloak Admin API.
              </p>
            </div>
          )}

          {/* Progress steps */}
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
                      ? `Initialization complete. ${createdCount} resource(s) created.`
                      : "All resources already exist. Nothing to do."
                  }
                </div>
              )}
            </div>
          )}

          {/* Loading indicator */}
          {initRunning && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground py-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              Initializing...
            </div>
          )}

          <DialogFooter>
            {initSteps.length === 0 ? (
              <>
                <Button variant="outline" onClick={() => setInitOpen(false)}>Cancel</Button>
                <Button onClick={handleInitialize} disabled={initRunning || !initAdminUser || !initAdminPass}>
                  {initRunning ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Rocket className="h-4 w-4 mr-1" />}
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
