"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { Eye, Loader2, Save, ShieldCheck, Trash2, Upload } from "lucide-react"

import { Button } from "@workspace/ui/components/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@workspace/ui/components/card"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"

import {
  deleteCaCert,
  deleteCaKey,
  fetchCaCertStatus,
  fetchCaKeyStatus,
  fetchSecurityConfig,
  generateSelfSignedCa,
  updateSecurityConfig,
  uploadCaCert,
  uploadCaKey,
  viewCaCert,
  viewCaKey,
} from "@/features/settings/api"
import type { CaCertViewData, CaKeyViewData } from "@/features/settings/api"

// --------------------------------------------------------------------------- //
// Error Dialog
// --------------------------------------------------------------------------- //

function ErrorDialog({
  open,
  message,
  onClose,
}: {
  open: boolean
  message: string
  onClose: () => void
}) {
  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent showCloseButton={false} className="max-w-sm">
        <DialogHeader>
          <DialogTitle>Error</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-destructive">{message}</p>
        <DialogFooter>
          <Button size="sm" onClick={onClose}>
            OK
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// --------------------------------------------------------------------------- //
// View Certificate Dialog
// --------------------------------------------------------------------------- //

function ViewCertDialog({
  open,
  data,
  onClose,
}: {
  open: boolean
  data: CaCertViewData | null
  onClose: () => void
}) {
  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-3xl max-h-[80vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle>CA Certificate</DialogTitle>
        </DialogHeader>
        <div className="flex-1 overflow-y-auto space-y-4 min-h-0">
          <div className="space-y-1.5">
            <Label className="text-xs font-medium text-muted-foreground">Certificate (PEM)</Label>
            <pre className="rounded-md border bg-muted/50 p-3 text-xs font-mono whitespace-pre-wrap break-all max-h-48 overflow-y-auto">
              {data?.raw ?? ""}
            </pre>
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs font-medium text-muted-foreground">
              Decoded (openssl x509 -text -noout)
            </Label>
            <pre className="rounded-md border bg-muted/50 p-3 text-xs font-mono whitespace-pre-wrap break-all max-h-64 overflow-y-auto">
              {data?.decoded ?? ""}
            </pre>
          </div>
        </div>
        <DialogFooter>
          <Button size="sm" variant="outline" onClick={onClose}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// --------------------------------------------------------------------------- //
// View Key Dialog
// --------------------------------------------------------------------------- //

function ViewKeyDialog({
  open,
  data,
  onClose,
}: {
  open: boolean
  data: CaKeyViewData | null
  onClose: () => void
}) {
  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-3xl max-h-[80vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle>CA Key</DialogTitle>
        </DialogHeader>
        <div className="flex-1 overflow-y-auto space-y-4 min-h-0">
          <div className="space-y-1.5">
            <Label className="text-xs font-medium text-muted-foreground">Key (PEM)</Label>
            <pre className="rounded-md border bg-muted/50 p-3 text-xs font-mono whitespace-pre-wrap break-all max-h-48 overflow-y-auto">
              {data?.raw ?? ""}
            </pre>
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs font-medium text-muted-foreground">
              Decoded (openssl rsa -text -noout)
            </Label>
            <pre className="rounded-md border bg-muted/50 p-3 text-xs font-mono whitespace-pre-wrap break-all max-h-64 overflow-y-auto">
              {data?.decoded ?? ""}
            </pre>
          </div>
        </div>
        <DialogFooter>
          <Button size="sm" variant="outline" onClick={onClose}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// --------------------------------------------------------------------------- //
// Generate Self-Signed CA Dialog
// --------------------------------------------------------------------------- //

const DEFAULT_GEN_FORM = {
  country: "KR",
  state: "Gyeonggi-do",
  locality: "Yongin-si",
  organization: "Open Cloud Engine Community",
  org_unit: "Platform Engineering",
  common_name: "Open Cloud Engine Community CA",
  days: "3650",
  key_bits: "4096",
}

function GenerateCaDialog({
  open,
  generating,
  onClose,
  onGenerate,
}: {
  open: boolean
  generating: boolean
  onClose: () => void
  onGenerate: (params: {
    country: string
    state: string
    locality: string
    organization: string
    org_unit: string
    common_name: string
    days: number
    key_bits: number
  }) => void
}) {
  const [form, setForm] = useState(DEFAULT_GEN_FORM)

  function handleChange(key: keyof typeof form, value: string) {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  function handleGenerate() {
    onGenerate({
      country: form.country,
      state: form.state,
      locality: form.locality,
      organization: form.organization,
      org_unit: form.org_unit,
      common_name: form.common_name,
      days: parseInt(form.days, 10) || 3650,
      key_bits: parseInt(form.key_bits, 10) || 4096,
    })
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-lg max-h-[85vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle>Generate Self-Signed CA</DialogTitle>
        </DialogHeader>
        <div className="flex-1 overflow-y-auto space-y-4 min-h-0 pr-1">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="gen-country" className="text-xs">Country (C)</Label>
              <Input
                id="gen-country"
                value={form.country}
                onChange={(e) => handleChange("country", e.target.value)}
                placeholder="KR"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="gen-state" className="text-xs">State (ST)</Label>
              <Input
                id="gen-state"
                value={form.state}
                onChange={(e) => handleChange("state", e.target.value)}
                placeholder="Gyeonggi-do"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="gen-locality" className="text-xs">Locality (L)</Label>
              <Input
                id="gen-locality"
                value={form.locality}
                onChange={(e) => handleChange("locality", e.target.value)}
                placeholder="Yongin-si"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="gen-org" className="text-xs">Organization (O)</Label>
              <Input
                id="gen-org"
                value={form.organization}
                onChange={(e) => handleChange("organization", e.target.value)}
                placeholder="Open Cloud Engine Community"
              />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="gen-ou" className="text-xs">Organizational Unit (OU)</Label>
            <Input
              id="gen-ou"
              value={form.org_unit}
              onChange={(e) => handleChange("org_unit", e.target.value)}
              placeholder="Platform Engineering"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="gen-cn" className="text-xs">Common Name (CN)</Label>
            <Input
              id="gen-cn"
              value={form.common_name}
              onChange={(e) => handleChange("common_name", e.target.value)}
              placeholder="Open Cloud Engine Community CA"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="gen-days" className="text-xs">Validity (days)</Label>
              <Input
                id="gen-days"
                type="number"
                value={form.days}
                onChange={(e) => handleChange("days", e.target.value)}
                placeholder="3650"
                min={1}
                max={36500}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="gen-bits" className="text-xs">RSA Key Bits</Label>
              <Input
                id="gen-bits"
                type="number"
                value={form.key_bits}
                onChange={(e) => handleChange("key_bits", e.target.value)}
                placeholder="4096"
                min={2048}
                step={1024}
              />
            </div>
          </div>
        </div>
        <DialogFooter className="gap-2">
          <Button size="sm" variant="outline" onClick={onClose} disabled={generating}>
            Cancel
          </Button>
          <Button size="sm" onClick={handleGenerate} disabled={generating}>
            {generating ? (
              <Loader2 className="h-4 w-4 animate-spin mr-1.5" />
            ) : (
              <ShieldCheck className="h-4 w-4 mr-1.5" />
            )}
            Generate
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// --------------------------------------------------------------------------- //
// Main Component
// --------------------------------------------------------------------------- //

export function SecuritySettings() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // CA cert dir config
  const [certDir, setCertDir] = useState("/opt/argus-insight-server/certs")
  const [savingDir, setSavingDir] = useState(false)

  // CA cert file state
  const [certFilename, setCertFilename] = useState("")
  const [uploadingCert, setUploadingCert] = useState(false)

  // CA key file state
  const [keyFilename, setKeyFilename] = useState("")
  const [uploadingKey, setUploadingKey] = useState(false)

  // Dialogs
  const [errorDialog, setErrorDialog] = useState<{ open: boolean; message: string }>({
    open: false,
    message: "",
  })
  const [viewCertDialog, setViewCertDialog] = useState<{
    open: boolean
    loading: boolean
    data: CaCertViewData | null
  }>({ open: false, loading: false, data: null })
  const [viewKeyDialog, setViewKeyDialog] = useState<{
    open: boolean
    loading: boolean
    data: CaKeyViewData | null
  }>({ open: false, loading: false, data: null })

  // Generate dialog
  const [generateDialog, setGenerateDialog] = useState(false)
  const [generating, setGenerating] = useState(false)

  // Status messages
  const [statusMessage, setStatusMessage] = useState<{
    type: "success" | "error"
    text: string
  } | null>(null)

  const certFileInputRef = useRef<HTMLInputElement>(null)
  const keyFileInputRef = useRef<HTMLInputElement>(null)

  function showStatus(type: "success" | "error", text: string) {
    setStatusMessage({ type, text })
    setTimeout(() => setStatusMessage(null), 3000)
  }

  function showError(message: string) {
    setErrorDialog({ open: true, message })
  }

  const loadConfig = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)

      // Load security config (ca_cert_dir)
      const securityItems = await fetchSecurityConfig()
      if (securityItems.ca_cert_dir) {
        setCertDir(securityItems.ca_cert_dir)
      }

      // Load CA cert and key status
      const [certStatus, keyStatus] = await Promise.all([
        fetchCaCertStatus(),
        fetchCaKeyStatus(),
      ])
      setCertFilename(certStatus.filename)
      setKeyFilename(keyStatus.filename)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load configuration")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadConfig()
  }, [loadConfig])

  // Save cert directory path
  async function handleSaveDir() {
    setSavingDir(true)
    try {
      await updateSecurityConfig({ ca_cert_dir: certDir })
      showStatus("success", "CA certificate directory saved successfully")
    } catch (err) {
      showStatus("error", err instanceof Error ? err.message : "Failed to save")
    } finally {
      setSavingDir(false)
    }
  }

  // ---- Generate Self-Signed CA ----

  function handleOpenGenerate() {
    if (!certDir.trim()) {
      showError("Please specify the CA Certificate Directory path. This operation will delete all existing CA certificates and replace them with newly generated Self-Signed CA certificate and key.")
      return
    }
    setGenerateDialog(true)
  }

  async function handleGenerate(params: {
    country: string
    state: string
    locality: string
    organization: string
    org_unit: string
    common_name: string
    days: number
    key_bits: number
  }) {
    setGenerating(true)
    try {
      const result = await generateSelfSignedCa(params)
      setCertFilename(result.cert_filename)
      setKeyFilename(result.key_filename)
      setGenerateDialog(false)
      showStatus("success", "Self-signed CA generated successfully")
    } catch (err) {
      showError(err instanceof Error ? err.message : "Generation failed")
    } finally {
      setGenerating(false)
    }
  }

  // ---- CA Certificate handlers ----

  async function handleUploadCert(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    e.target.value = ""

    setUploadingCert(true)
    try {
      await uploadCaCert(file)
      showStatus("success", "CA certificate uploaded successfully")
      const status = await fetchCaCertStatus()
      setCertFilename(status.filename)
    } catch (err) {
      showError(err instanceof Error ? err.message : "Upload failed")
    } finally {
      setUploadingCert(false)
    }
  }

  async function handleViewCert() {
    setViewCertDialog({ open: true, loading: true, data: null })
    try {
      const data = await viewCaCert()
      setViewCertDialog({ open: true, loading: false, data })
    } catch (err) {
      setViewCertDialog({ open: false, loading: false, data: null })
      showError(err instanceof Error ? err.message : "Failed to view certificate")
    }
  }

  async function handleDeleteCert() {
    try {
      await deleteCaCert()
      setCertFilename("")
      showStatus("success", "CA certificate deleted successfully")
    } catch (err) {
      showError(err instanceof Error ? err.message : "Failed to delete certificate")
    }
  }

  // ---- CA Key handlers ----

  async function handleUploadKey(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    e.target.value = ""

    setUploadingKey(true)
    try {
      await uploadCaKey(file)
      showStatus("success", "CA key uploaded successfully")
      const status = await fetchCaKeyStatus()
      setKeyFilename(status.filename)
    } catch (err) {
      showError(err instanceof Error ? err.message : "Upload failed")
    } finally {
      setUploadingKey(false)
    }
  }

  async function handleViewKey() {
    setViewKeyDialog({ open: true, loading: true, data: null })
    try {
      const data = await viewCaKey()
      setViewKeyDialog({ open: true, loading: false, data })
    } catch (err) {
      setViewKeyDialog({ open: false, loading: false, data: null })
      showError(err instanceof Error ? err.message : "Failed to view key")
    }
  }

  async function handleDeleteKey() {
    try {
      await deleteCaKey()
      setKeyFilename("")
      showStatus("success", "CA key deleted successfully")
    } catch (err) {
      showError(err instanceof Error ? err.message : "Failed to delete key")
    }
  }

  // ---- Render ----

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
      {/* Status message */}
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

      {/* CA (Certificate Authority) */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>CA (Certificate Authority)</CardTitle>
              <CardDescription>
                Manage the CA certificate and key used for TLS/SSL operations
              </CardDescription>
            </div>
            <div className="flex gap-2">
              <Button size="sm" onClick={handleSaveDir} disabled={savingDir}>
                {savingDir ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-1.5" />
                ) : (
                  <Save className="h-4 w-4 mr-1.5" />
                )}
                Save
              </Button>
              <Button size="sm" variant="destructive" onClick={handleOpenGenerate}>
                <ShieldCheck className="h-4 w-4 mr-1.5" />
                Generate Self-Signed CA
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-6">
            {/* CA Certificate Directory */}
            <div className="space-y-2">
              <Label htmlFor="ca-cert-dir">CA Certificate Directory</Label>
              <Input
                id="ca-cert-dir"
                value={certDir}
                onChange={(e) => setCertDir(e.target.value)}
                placeholder="/opt/argus-insight-server/certs"
              />
              <p className="text-xs text-muted-foreground">
                Absolute path on the Argus Insight Server where CA certificates are stored
              </p>
            </div>

            {/* CA Certificate File */}
            <div className="space-y-2">
              <Label htmlFor="ca-cert-file">CA Certificate</Label>
              <div className="flex gap-2">
                <Input
                  id="ca-cert-file"
                  value={certFilename}
                  readOnly
                  placeholder="No certificate uploaded"
                  className="flex-1"
                />
                <input
                  ref={certFileInputRef}
                  type="file"
                  accept=".crt,.pem,.cer"
                  className="hidden"
                  onChange={handleUploadCert}
                />
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="h-9 px-3"
                  disabled={uploadingCert}
                  onClick={() => certFileInputRef.current?.click()}
                >
                  {uploadingCert ? (
                    <Loader2 className="h-4 w-4 animate-spin mr-1.5" />
                  ) : (
                    <Upload className="h-4 w-4 mr-1.5" />
                  )}
                  Upload
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="h-9 px-3"
                  disabled={!certFilename}
                  onClick={handleViewCert}
                >
                  <Eye className="h-4 w-4 mr-1.5" />
                  View
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="h-9 px-3 text-destructive hover:text-destructive"
                  disabled={!certFilename}
                  onClick={handleDeleteCert}
                >
                  <Trash2 className="h-4 w-4 mr-1.5" />
                  Delete
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                Upload a CA certificate file. The file will be validated using OpenSSL and saved as ca.crt.
              </p>
            </div>

            {/* CA Key File */}
            <div className="space-y-2">
              <Label htmlFor="ca-key-file">CA Key</Label>
              <div className="flex gap-2">
                <Input
                  id="ca-key-file"
                  value={keyFilename}
                  readOnly
                  placeholder="No key uploaded"
                  className="flex-1"
                />
                <input
                  ref={keyFileInputRef}
                  type="file"
                  accept=".key,.pem"
                  className="hidden"
                  onChange={handleUploadKey}
                />
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="h-9 px-3"
                  disabled={uploadingKey}
                  onClick={() => keyFileInputRef.current?.click()}
                >
                  {uploadingKey ? (
                    <Loader2 className="h-4 w-4 animate-spin mr-1.5" />
                  ) : (
                    <Upload className="h-4 w-4 mr-1.5" />
                  )}
                  Upload
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="h-9 px-3"
                  disabled={!keyFilename}
                  onClick={handleViewKey}
                >
                  <Eye className="h-4 w-4 mr-1.5" />
                  View
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="h-9 px-3 text-destructive hover:text-destructive"
                  disabled={!keyFilename}
                  onClick={handleDeleteKey}
                >
                  <Trash2 className="h-4 w-4 mr-1.5" />
                  Delete
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                Upload a CA key file. The file will be validated using OpenSSL and saved as ca.key.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Error Dialog */}
      <ErrorDialog
        open={errorDialog.open}
        message={errorDialog.message}
        onClose={() => setErrorDialog({ open: false, message: "" })}
      />

      {/* View Certificate Dialog */}
      <ViewCertDialog
        open={viewCertDialog.open && !viewCertDialog.loading}
        data={viewCertDialog.data}
        onClose={() => setViewCertDialog({ open: false, loading: false, data: null })}
      />

      {/* View Key Dialog */}
      <ViewKeyDialog
        open={viewKeyDialog.open && !viewKeyDialog.loading}
        data={viewKeyDialog.data}
        onClose={() => setViewKeyDialog({ open: false, loading: false, data: null })}
      />

      {/* Generate Self-Signed CA Dialog */}
      <GenerateCaDialog
        open={generateDialog}
        generating={generating}
        onClose={() => setGenerateDialog(false)}
        onGenerate={handleGenerate}
      />

      {/* Loading overlay for view dialogs */}
      {((viewCertDialog.open && viewCertDialog.loading) ||
        (viewKeyDialog.open && viewKeyDialog.loading)) && (
        <Dialog open>
          <DialogContent showCloseButton={false} className="max-w-xs">
            <div className="flex items-center justify-center py-6 gap-2">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              <span className="text-sm text-muted-foreground">Loading...</span>
            </div>
          </DialogContent>
        </Dialog>
      )}
    </div>
  )
}
