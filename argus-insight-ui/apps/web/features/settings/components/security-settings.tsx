"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { Eye, Loader2, Save, Trash2, Upload } from "lucide-react"

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
  fetchCaCertStatus,
  fetchInfraConfig,
  updateInfraCategory,
  uploadCaCert,
  viewCaCert,
} from "@/features/settings/api"
import type { CaCertViewData } from "@/features/settings/api"

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
          {/* Raw PEM content */}
          <div className="space-y-1.5">
            <Label className="text-xs font-medium text-muted-foreground">Certificate (PEM)</Label>
            <pre className="rounded-md border bg-muted/50 p-3 text-xs font-mono whitespace-pre-wrap break-all max-h-48 overflow-y-auto">
              {data?.raw ?? ""}
            </pre>
          </div>
          {/* Decoded openssl output */}
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
  const [uploading, setUploading] = useState(false)

  // Dialogs
  const [errorDialog, setErrorDialog] = useState<{ open: boolean; message: string }>({
    open: false,
    message: "",
  })
  const [viewDialog, setViewDialog] = useState<{
    open: boolean
    loading: boolean
    data: CaCertViewData | null
  }>({ open: false, loading: false, data: null })

  // Status messages
  const [statusMessage, setStatusMessage] = useState<{
    type: "success" | "error"
    text: string
  } | null>(null)

  const fileInputRef = useRef<HTMLInputElement>(null)

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

      // Load infra config for security category (ca_cert_dir)
      const infraData = await fetchInfraConfig()
      const securityCat = infraData.categories.find((c) => c.category === "security")
      if (securityCat?.items.ca_cert_dir) {
        setCertDir(securityCat.items.ca_cert_dir)
      }

      // Load CA cert status
      const status = await fetchCaCertStatus()
      setCertFilename(status.filename)
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
      await updateInfraCategory("security", { ca_cert_dir: certDir })
      showStatus("success", "CA certificate directory saved successfully")
    } catch (err) {
      showStatus("error", err instanceof Error ? err.message : "Failed to save")
    } finally {
      setSavingDir(false)
    }
  }

  // Upload CA cert
  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return

    // Reset file input so the same file can be re-selected
    e.target.value = ""

    setUploading(true)
    try {
      await uploadCaCert(file)
      showStatus("success", "CA certificate uploaded successfully")
      // Refresh status
      const status = await fetchCaCertStatus()
      setCertFilename(status.filename)
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Upload failed"
      showError(msg)
    } finally {
      setUploading(false)
    }
  }

  // View CA cert
  async function handleView() {
    setViewDialog({ open: true, loading: true, data: null })
    try {
      const data = await viewCaCert()
      setViewDialog({ open: true, loading: false, data })
    } catch (err) {
      setViewDialog({ open: false, loading: false, data: null })
      const msg = err instanceof Error ? err.message : "Failed to view certificate"
      showError(msg)
    }
  }

  // Delete CA cert
  async function handleDelete() {
    try {
      await deleteCaCert()
      setCertFilename("")
      showStatus("success", "CA certificate deleted successfully")
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to delete certificate"
      showError(msg)
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
                Manage the CA certificate used for TLS/SSL operations
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-6">
            {/* CA Certificate Directory */}
            <div className="space-y-2">
              <Label htmlFor="ca-cert-dir">CA Certificate Directory</Label>
              <div className="flex gap-2">
                <Input
                  id="ca-cert-dir"
                  value={certDir}
                  onChange={(e) => setCertDir(e.target.value)}
                  placeholder="/opt/argus-insight-server/certs"
                  className="flex-1"
                />
                <Button size="sm" className="h-9" onClick={handleSaveDir} disabled={savingDir}>
                  {savingDir ? (
                    <Loader2 className="h-4 w-4 animate-spin mr-1.5" />
                  ) : (
                    <Save className="h-4 w-4 mr-1.5" />
                  )}
                  Save
                </Button>
              </div>
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
                {/* Hidden file input */}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".crt,.pem,.cer"
                  className="hidden"
                  onChange={handleUpload}
                />
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="h-9 px-3"
                  disabled={uploading}
                  onClick={() => fileInputRef.current?.click()}
                >
                  {uploading ? (
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
                  onClick={handleView}
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
                  onClick={handleDelete}
                >
                  <Trash2 className="h-4 w-4 mr-1.5" />
                  Delete
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                Upload a CA certificate file. The file will be validated using OpenSSL and saved as ca.crt.
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
        open={viewDialog.open}
        data={viewDialog.data}
        onClose={() => setViewDialog({ open: false, loading: false, data: null })}
      />

      {/* Loading overlay for view dialog */}
      {viewDialog.open && viewDialog.loading && (
        <Dialog open>
          <DialogContent showCloseButton={false} className="max-w-xs">
            <div className="flex items-center justify-center py-6 gap-2">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              <span className="text-sm text-muted-foreground">Loading certificate...</span>
            </div>
          </DialogContent>
        </Dialog>
      )}
    </div>
  )
}
