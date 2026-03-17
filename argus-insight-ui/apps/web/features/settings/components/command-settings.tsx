"use client"

import { useCallback, useEffect, useState } from "react"
import { CheckCircle2, Loader2, Save, Search, XCircle } from "lucide-react"

import { Button } from "@workspace/ui/components/button"
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"

import { checkPath, fetchInfraConfig, updateInfraCategory } from "@/features/settings/api"

// --------------------------------------------------------------------------- //
// Types
// --------------------------------------------------------------------------- //

type CommandEntry = {
  key: string
  label: string
  description: string
  value: string
  checkResult: "none" | "checking" | "exists" | "not_found"
}

const COMMAND_DEFAULTS: { key: string; label: string; description: string; defaultValue: string }[] = [
  { key: "openssl_path", label: "OpenSSL", description: "Used for generating and verifying CA certificates and server certificates.", defaultValue: "/usr/bin/openssl" },
]

// --------------------------------------------------------------------------- //
// Main Component
// --------------------------------------------------------------------------- //

export function CommandSettings() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const [commands, setCommands] = useState<CommandEntry[]>([])

  // Status messages
  const [statusMessage, setStatusMessage] = useState<{ type: "success" | "error"; text: string } | null>(null)

  const loadConfig = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await fetchInfraConfig()
      const cat = data.categories.find((c) => c.category === "command")
      setCommands(
        COMMAND_DEFAULTS.map((def) => ({
          key: def.key,
          label: def.label,
          description: def.description,
          value: cat?.items[def.key] ?? def.defaultValue,
          checkResult: "none",
        })),
      )
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

  function updateCommand(key: string, value: string) {
    setCommands((prev) =>
      prev.map((c) => (c.key === key ? { ...c, value, checkResult: "none" } : c)),
    )
  }

  async function handleCheck(key: string) {
    const entry = commands.find((c) => c.key === key)
    if (!entry || !entry.value.trim()) return

    setCommands((prev) =>
      prev.map((c) => (c.key === key ? { ...c, checkResult: "checking" } : c)),
    )
    try {
      const exists = await checkPath(entry.value)
      setCommands((prev) =>
        prev.map((c) =>
          c.key === key ? { ...c, checkResult: exists ? "exists" : "not_found" } : c,
        ),
      )
    } catch {
      setCommands((prev) =>
        prev.map((c) => (c.key === key ? { ...c, checkResult: "not_found" } : c)),
      )
    }
  }

  async function handleSave() {
    setSaving(true)
    try {
      const items: Record<string, string> = {}
      for (const cmd of commands) {
        items[cmd.key] = cmd.value
      }
      await updateInfraCategory("command", items)
      showStatus("success", "Command settings saved successfully")
      await loadConfig()
    } catch (err) {
      showStatus("error", err instanceof Error ? err.message : "Failed to save")
    } finally {
      setSaving(false)
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

      {/* Save button */}
      <div className="flex justify-end">
        <Button size="sm" onClick={handleSave} disabled={saving}>
          {saving ? (
            <Loader2 className="h-4 w-4 animate-spin mr-1.5" />
          ) : (
            <Save className="h-4 w-4 mr-1.5" />
          )}
          Save
        </Button>
      </div>

      {/* Command entries */}
      {commands.map((cmd) => (
        <div key={cmd.key} className="space-y-1.5">
          <Label htmlFor={`cmd-${cmd.key}`}>{cmd.label}</Label>
          <p className="text-xs text-muted-foreground">{cmd.description}</p>
          <div className="flex gap-2">
            <Input
              id={`cmd-${cmd.key}`}
              value={cmd.value}
              onChange={(e) => updateCommand(cmd.key, e.target.value)}
              placeholder={`Path to ${cmd.label}`}
              className="flex-1"
            />
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="h-9 px-3"
              disabled={cmd.checkResult === "checking" || !cmd.value.trim()}
              onClick={() => handleCheck(cmd.key)}
            >
              {cmd.checkResult === "checking" ? (
                <Loader2 className="h-4 w-4 animate-spin mr-1.5" />
              ) : (
                <Search className="h-4 w-4 mr-1.5" />
              )}
              Check
            </Button>
          </div>
          {cmd.checkResult === "exists" && (
            <div className="flex items-center gap-1.5 text-xs text-green-600 dark:text-green-400">
              <CheckCircle2 className="h-3.5 w-3.5" />
              파일이 존재합니다
            </div>
          )}
          {cmd.checkResult === "not_found" && (
            <div className="flex items-center gap-1.5 text-xs text-destructive">
              <XCircle className="h-3.5 w-3.5" />
              파일이 존재하지 않습니다
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
