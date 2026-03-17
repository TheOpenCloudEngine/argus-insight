"use client"

import { useCallback, useEffect, useState } from "react"
import { Loader2, Save } from "lucide-react"

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@workspace/ui/components/alert-dialog"
import { Button } from "@workspace/ui/components/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@workspace/ui/components/card"
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"

import {
  fetchDomainConfig,
  fetchPowerDnsConfig,
  updateDomainConfig,
  updatePowerDnsConfig,
} from "@/features/settings/api"

const DNS_SERVER_COUNT = 3

// --------------------------------------------------------------------------- //
// Validation helpers
// --------------------------------------------------------------------------- //

const IP_REGEX = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/

function isValidIp(value: string): boolean {
  const match = value.match(IP_REGEX)
  if (!match) return false
  return match.slice(1).every((octet) => {
    const n = parseInt(octet, 10)
    return n >= 0 && n <= 255
  })
}

function isValidPort(value: string): boolean {
  const n = parseInt(value, 10)
  return Number.isInteger(n) && n >= 1 && n <= 65535 && String(n) === value
}

// --------------------------------------------------------------------------- //
// Domain Settings Section
// --------------------------------------------------------------------------- //

function DomainSettingsSection({
  domainName,
  onDomainNameChange,
  onSave,
  saving,
}: {
  domainName: string
  onDomainNameChange: (value: string) => void
  onSave: () => void
  saving: boolean
}) {
  const [confirmOpen, setConfirmOpen] = useState(false)

  const trimmed = domainName.trim()
  const canSave = trimmed.length > 0

  function handleSaveClick() {
    setConfirmOpen(true)
  }

  function handleConfirm() {
    setConfirmOpen(false)
    onSave()
  }

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Domain</CardTitle>
              <CardDescription>
                Domain name configuration
              </CardDescription>
            </div>
            <Button size="sm" onClick={handleSaveClick} disabled={saving || !canSave}>
              {saving ? (
                <Loader2 className="h-4 w-4 animate-spin mr-1.5" />
              ) : (
                <Save className="h-4 w-4 mr-1.5" />
              )}
              Save
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <Label htmlFor="infra-domain-name">Domain Name</Label>
            <Input
              id="infra-domain-name"
              value={domainName}
              onChange={(e) => onDomainNameChange(e.target.value)}
              placeholder="e.g. example.com"
            />
            <p className="text-xs text-muted-foreground">
              The primary domain name for this infrastructure
            </p>
          </div>
        </CardContent>
      </Card>

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Domain Name 변경 확인</AlertDialogTitle>
            <AlertDialogDescription>
              Domain Name을 변경하면 시스템 전체에 영향을 받을 수 있습니다. 인증서 및 호스트명 등에 영향을 줄 수 있습니다. 계속 진행하시겠습니까?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>No</AlertDialogCancel>
            <AlertDialogAction onClick={handleConfirm}>Yes</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}

// --------------------------------------------------------------------------- //
// DNS Servers Section
// --------------------------------------------------------------------------- //

function DnsServersSection({
  dnsServers,
  onDnsServerChange,
  onSave,
  saving,
}: {
  dnsServers: [string, string, string]
  onDnsServerChange: (index: number, value: string) => void
  onSave: () => void
  saving: boolean
}) {
  // Compute validation state for each server
  const validations = dnsServers.map((s) => {
    const trimmed = s.trim()
    if (trimmed === "") return { hasValue: false, valid: true }
    return { hasValue: true, valid: isValidIp(trimmed) }
  })

  const hasAtLeastOneValid = validations.some((v) => v.hasValue && v.valid)
  const hasInvalid = validations.some((v) => v.hasValue && !v.valid)
  const canSave = hasAtLeastOneValid && !hasInvalid

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>DNS Servers</CardTitle>
            <CardDescription>
              Configure up to {DNS_SERVER_COUNT} DNS servers
            </CardDescription>
          </div>
          <Button size="sm" onClick={onSave} disabled={saving || !canSave}>
            {saving ? (
              <Loader2 className="h-4 w-4 animate-spin mr-1.5" />
            ) : (
              <Save className="h-4 w-4 mr-1.5" />
            )}
            Save
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid gap-3 sm:grid-cols-3">
          {Array.from({ length: DNS_SERVER_COUNT }, (_, i) => {
            const v = validations[i]
            return (
              <div key={i} className="space-y-1.5">
                <Label htmlFor={`dns-server-${i + 1}`}>
                  DNS Server {i + 1}
                </Label>
                <Input
                  id={`dns-server-${i + 1}`}
                  value={dnsServers[i]}
                  onChange={(e) => onDnsServerChange(i, e.target.value)}
                  placeholder={`e.g. 8.8.${i === 0 ? "8.8" : i === 1 ? "4.4" : "0.0"}`}
                />
                {v.hasValue && !v.valid && (
                  <p className="text-xs text-destructive">
                    IP 주소 형식이 아닙니다
                  </p>
                )}
              </div>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}

// --------------------------------------------------------------------------- //
// PowerDNS Settings Section
// --------------------------------------------------------------------------- //

function PowerDnsSettingsSection({
  values,
  onChange,
  onSave,
  saving,
}: {
  values: { ip: string; port: string; api_key: string; server_id: string }
  onChange: (key: string, value: string) => void
  onSave: () => void
  saving: boolean
}) {
  const ipTrimmed = values.ip.trim()
  const portTrimmed = values.port.trim()
  const apiKeyTrimmed = values.api_key.trim()

  const ipHasValue = ipTrimmed.length > 0
  const portHasValue = portTrimmed.length > 0
  const apiKeyHasValue = apiKeyTrimmed.length > 0

  const ipValid = !ipHasValue || isValidIp(ipTrimmed)
  const portValid = !portHasValue || isValidPort(portTrimmed)

  const canSave =
    ipHasValue && portHasValue && apiKeyHasValue &&
    ipValid && portValid

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>PowerDNS</CardTitle>
            <CardDescription>
              PowerDNS server connection settings
            </CardDescription>
          </div>
          <Button size="sm" onClick={onSave} disabled={saving || !canSave}>
            {saving ? (
              <Loader2 className="h-4 w-4 animate-spin mr-1.5" />
            ) : (
              <Save className="h-4 w-4 mr-1.5" />
            )}
            Save
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="pdns-ip">
              PowerDNS IP <span className="text-destructive">*</span>
            </Label>
            <Input
              id="pdns-ip"
              value={values.ip}
              onChange={(e) => onChange("ip", e.target.value)}
              placeholder="e.g. 10.0.1.50"
            />
            {ipHasValue && !ipValid && (
              <p className="text-xs text-destructive">
                IP 주소 형식이 아닙니다
              </p>
            )}
          </div>
          <div className="space-y-2">
            <Label htmlFor="pdns-port">
              PowerDNS Port <span className="text-destructive">*</span>
            </Label>
            <Input
              id="pdns-port"
              type="number"
              min={1}
              max={65535}
              value={values.port}
              onChange={(e) => onChange("port", e.target.value)}
              placeholder="e.g. 8081"
            />
            {portHasValue && !portValid && (
              <p className="text-xs text-destructive">
                유효한 포트 번호가 아닙니다 (1-65535)
              </p>
            )}
          </div>
          <div className="space-y-2">
            <Label htmlFor="pdns-api-key">
              API Key <span className="text-destructive">*</span>
            </Label>
            <Input
              id="pdns-api-key"
              type="password"
              value={values.api_key}
              onChange={(e) => onChange("api_key", e.target.value)}
              placeholder="PowerDNS API key"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="pdns-server-id">Server ID</Label>
            <Input
              id="pdns-server-id"
              value={values.server_id}
              onChange={(e) => onChange("server_id", e.target.value)}
              placeholder="e.g. localhost"
            />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

// --------------------------------------------------------------------------- //
// Main Component
// --------------------------------------------------------------------------- //

export function DomainSettings() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [savingDomain, setSavingDomain] = useState(false)
  const [savingDns, setSavingDns] = useState(false)
  const [savingPdns, setSavingPdns] = useState(false)

  // Domain state
  const [domainName, setDomainName] = useState("")
  const [dnsServers, setDnsServers] = useState<[string, string, string]>(["", "", ""])

  // PowerDNS state
  const [pdns, setPdns] = useState({ ip: "", port: "", api_key: "", server_id: "" })

  // Status messages
  const [statusMessage, setStatusMessage] = useState<{ type: "success" | "error"; text: string } | null>(null)

  const loadConfig = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const [domain, powerdns] = await Promise.all([
        fetchDomainConfig(),
        fetchPowerDnsConfig(),
      ])

      setDomainName(domain.domain_name ?? "")
      setDnsServers([
        domain.dns_server_1 ?? "",
        domain.dns_server_2 ?? "",
        domain.dns_server_3 ?? "",
      ])

      setPdns({
        ip: powerdns.pdns_ip ?? "",
        port: powerdns.pdns_port ?? "",
        api_key: powerdns.pdns_api_key ?? "",
        server_id: powerdns.pdns_server_id ?? "",
      })
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

  async function handleSaveDomain() {
    setSavingDomain(true)
    try {
      await updateDomainConfig({
        domain_name: domainName,
        dns_server_1: dnsServers[0],
        dns_server_2: dnsServers[1],
        dns_server_3: dnsServers[2],
      })
      showStatus("success", "Domain settings saved successfully")
      await loadConfig()
    } catch (err) {
      showStatus("error", err instanceof Error ? err.message : "Failed to save")
    } finally {
      setSavingDomain(false)
    }
  }

  async function handleSaveDns() {
    setSavingDns(true)
    try {
      await updateDomainConfig({
        domain_name: domainName,
        dns_server_1: dnsServers[0],
        dns_server_2: dnsServers[1],
        dns_server_3: dnsServers[2],
      })
      showStatus("success", "DNS server settings saved successfully")
      await loadConfig()
    } catch (err) {
      showStatus("error", err instanceof Error ? err.message : "Failed to save")
    } finally {
      setSavingDns(false)
    }
  }

  async function handleSavePdns() {
    setSavingPdns(true)
    try {
      await updatePowerDnsConfig({
        pdns_ip: pdns.ip,
        pdns_port: pdns.port,
        pdns_api_key: pdns.api_key,
        pdns_server_id: pdns.server_id,
      })
      showStatus("success", "PowerDNS settings saved successfully")
      await loadConfig()
    } catch (err) {
      showStatus("error", err instanceof Error ? err.message : "Failed to save")
    } finally {
      setSavingPdns(false)
    }
  }

  function handleDnsServerChange(index: number, value: string) {
    setDnsServers((prev) => {
      const next: [string, string, string] = [...prev]
      next[index] = value
      return next
    })
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

      {/* Domain Settings */}
      <DomainSettingsSection
        domainName={domainName}
        onDomainNameChange={setDomainName}
        onSave={handleSaveDomain}
        saving={savingDomain}
      />

      {/* DNS Servers */}
      <DnsServersSection
        dnsServers={dnsServers}
        onDnsServerChange={handleDnsServerChange}
        onSave={handleSaveDns}
        saving={savingDns}
      />

      {/* PowerDNS Settings */}
      <PowerDnsSettingsSection
        values={pdns}
        onChange={(key, value) => setPdns((prev) => ({ ...prev, [key]: value }))}
        onSave={handleSavePdns}
        saving={savingPdns}
      />
    </div>
  )
}
