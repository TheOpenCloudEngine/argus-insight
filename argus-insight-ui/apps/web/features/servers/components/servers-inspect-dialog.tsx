"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import {
  Cpu,
  HardDrive,
  Info,
  Loader2,
  Monitor,
  Network,
  ScrollText,
  Server,
  Shield,
  Terminal,
  Users,
} from "lucide-react"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@workspace/ui/components/sheet"
import { Badge } from "@workspace/ui/components/badge"
import { Separator } from "@workspace/ui/components/separator"
import { fetchInspect } from "../api"
import { type Server as ServerType } from "../data/schema"

type ServersInspectDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  currentRow: ServerType
}

/* eslint-disable @typescript-eslint/no-explicit-any */

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B"
  const k = 1024
  const sizes = ["B", "KB", "MB", "GB", "TB"]
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`
}

function Section({
  icon: Icon,
  title,
  children,
}: {
  icon: React.ElementType
  title: string
  children: React.ReactNode
}) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
        <Icon className="h-4 w-4 text-muted-foreground" />
        {title}
      </div>
      <div className="rounded-lg border bg-card">{children}</div>
    </div>
  )
}

function Field({ label, value, mono }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-start justify-between gap-4 px-4 py-2.5 text-sm border-b last:border-b-0">
      <span className="text-muted-foreground shrink-0">{label}</span>
      <span className={`text-right break-all ${mono ? "font-mono text-xs" : ""}`}>{value}</span>
    </div>
  )
}

function PreBlock({ content, maxHeight = "200px" }: { content: string; maxHeight?: string }) {
  return (
    <pre
      className="overflow-auto rounded-md bg-muted p-3 text-xs font-mono leading-relaxed"
      style={{ maxHeight }}
    >
      {content || "(empty)"}
    </pre>
  )
}

export function ServersInspectDialog({
  open,
  onOpenChange,
  currentRow,
}: ServersInspectDialogProps) {
  const [data, setData] = useState<Record<string, any> | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadInspect = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await fetchInspect(currentRow.hostname)
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load inspection data")
    } finally {
      setLoading(false)
    }
  }, [currentRow.hostname])

  useEffect(() => {
    if (open) {
      loadInspect()
    } else {
      setData(null)
      setError(null)
    }
  }, [open, loadInspect])

  const hostname = data?.hostname as any
  const resourceUsage = data?.resource_usage as any
  const ipAddresses = (data?.ip_addresses ?? []) as any[]
  const nameservers = (data?.nameservers ?? []) as any[]
  const diskPartitions = (data?.disk_partitions ?? []) as any[]
  const processes = (data?.processes ?? []) as any[]
  const ulimits = (data?.ulimits ?? []) as any[]
  const networkInterfaces = (data?.network_interfaces ?? []) as any[]

  const [width, setWidth] = useState(800)
  const dragging = useRef(false)
  const startX = useRef(0)
  const startWidth = useRef(0)

  useEffect(() => {
    if (!open) {
      setWidth(800)
      return
    }

    const onMouseMove = (e: MouseEvent) => {
      if (!dragging.current) return
      const delta = startX.current - e.clientX
      const newWidth = Math.max(400, Math.min(startWidth.current + delta, window.innerWidth - 40))
      setWidth(newWidth)
    }

    const onMouseUp = () => {
      dragging.current = false
      document.body.style.cursor = ""
      document.body.style.userSelect = ""
    }

    document.addEventListener("mousemove", onMouseMove)
    document.addEventListener("mouseup", onMouseUp)
    return () => {
      document.removeEventListener("mousemove", onMouseMove)
      document.removeEventListener("mouseup", onMouseUp)
    }
  }, [open])

  const handleDragStart = (e: React.MouseEvent) => {
    dragging.current = true
    startX.current = e.clientX
    startWidth.current = width
    document.body.style.cursor = "col-resize"
    document.body.style.userSelect = "none"
    e.preventDefault()
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="overflow-y-auto px-5 !w-auto"
        style={{ width, maxWidth: "none" }}
      >
        {/* Drag handle on the left edge */}
        <div
          className="absolute left-0 top-0 bottom-0 w-1.5 cursor-col-resize hover:bg-primary/20 active:bg-primary/30 transition-colors"
          onMouseDown={handleDragStart}
        />
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <Monitor className="h-5 w-5" />
            Host Inspection
          </SheetTitle>
          <SheetDescription>
            {currentRow.hostname} ({currentRow.ipAddress})
          </SheetDescription>
        </SheetHeader>

        {loading && (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            <span className="ml-2 text-sm text-muted-foreground">Inspecting host...</span>
          </div>
        )}

        {error && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/5 p-4 text-sm text-destructive">
            {error}
          </div>
        )}

        {data && !loading && (
          <div className="space-y-6 pb-6">
            {/* 1. Hostname & IP */}
            <Section icon={Server} title="Hostname & Network Identity">
              <Field label="Hostname" value={hostname?.hostname} mono />
              <Field label="FQDN" value={hostname?.fqdn} mono />
              <Field
                label="Consistent"
                value={
                  <Badge variant={hostname?.is_consistent ? "default" : "destructive"}>
                    {hostname?.is_consistent ? "Yes" : "No"}
                  </Badge>
                }
              />
              {ipAddresses.map((ip: any, i: number) => (
                <Field key={i} label={ip.interface} value={ip.address} mono />
              ))}
            </Section>

            {/* 2. Nameservers */}
            <Section icon={Network} title="Nameservers">
              {nameservers.length > 0 ? (
                nameservers.map((ns: any, i: number) => (
                  <Field key={i} label={`Nameserver ${i + 1}`} value={ns.address} mono />
                ))
              ) : (
                <div className="px-4 py-2.5 text-sm text-muted-foreground">No nameservers configured</div>
              )}
            </Section>

            {/* 3. Resource Usage */}
            <Section icon={Cpu} title="Resource Usage">
              <Field label="CPU Cores" value={resourceUsage?.cpu_cores} />
              <Field label="Total Memory" value={formatBytes(resourceUsage?.total_memory_bytes ?? 0)} />
              <Field
                label="CPU Usage"
                value={`${resourceUsage?.cpu_usage_percent?.toFixed(1)}%`}
              />
              <Field
                label="Memory Usage"
                value={`${resourceUsage?.memory_usage_percent?.toFixed(1)}%`}
              />
              <Field
                label="Swap Usage"
                value={`${resourceUsage?.swap_usage_percent?.toFixed(1)}%`}
              />
            </Section>

            {/* 4. Disk Partitions */}
            <Section icon={HardDrive} title="Disk Partitions">
              {diskPartitions.map((dp: any, i: number) => (
                <div key={i} className="px-4 py-2.5 border-b last:border-b-0">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-mono text-xs">{dp.device}</span>
                    <Badge variant="outline">{dp.fs_type}</Badge>
                  </div>
                  <div className="mt-1 flex items-center gap-3 text-xs text-muted-foreground">
                    <span>Mount: {dp.mount_point}</span>
                    <span>Total: {formatBytes(dp.total_bytes)}</span>
                    <span>Used: {dp.usage_percent?.toFixed(1)}%</span>
                  </div>
                </div>
              ))}
            </Section>

            {/* 5. Ulimit */}
            <Section icon={Shield} title="Ulimit">
              {ulimits.map((ul: any, i: number) => (
                <Field
                  key={i}
                  label={`${ul.resource} (${ul.option})`}
                  value={`soft=${ul.soft} / hard=${ul.hard}`}
                  mono
                />
              ))}
            </Section>

            {/* 6. Network Interfaces */}
            <Section icon={Network} title="Network Interfaces (ifconfig)">
              {networkInterfaces.map((iface: any, i: number) => (
                <div key={i} className="px-4 py-2.5 border-b last:border-b-0">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-semibold">{iface.name}</span>
                    {iface.flags && (
                      <span className="text-xs text-muted-foreground">{iface.flags}</span>
                    )}
                  </div>
                  <div className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-muted-foreground font-mono">
                    {iface.inet && <span>inet {iface.inet}</span>}
                    {iface.netmask && <span>netmask {iface.netmask}</span>}
                    {iface.ether && <span>ether {iface.ether}</span>}
                    {iface.mtu && <span>mtu {iface.mtu}</span>}
                  </div>
                </div>
              ))}
            </Section>

            {/* 7. uname -a */}
            <Section icon={Info} title="System Info (uname -a)">
              <div className="p-3">
                <PreBlock content={data.uname as string} maxHeight="80px" />
              </div>
            </Section>

            {/* 8. Process List */}
            <Section icon={Terminal} title={`Processes (${processes.length})`}>
              <div className="p-3">
                <PreBlock
                  content={
                    "UID        PID  PPID  C STIME TTY      TIME     CMD\n" +
                    processes
                      .map(
                        (p: any) =>
                          `${p.uid.padEnd(9)} ${String(p.pid).padStart(5)} ${String(p.ppid).padStart(5)}  ${p.c} ${p.stime.padEnd(5)} ${p.tty.padEnd(8)} ${p.time.padEnd(8)} ${p.cmd}`
                      )
                      .join("\n")
                  }
                  maxHeight="300px"
                />
              </div>
            </Section>

            {/* 9. Environment Variables */}
            <Section icon={ScrollText} title="Environment Variables (set)">
              <div className="p-3">
                <PreBlock content={data.env_variables as string} maxHeight="300px" />
              </div>
            </Section>

            {/* 10. sysctl.conf */}
            <Section icon={Shield} title="/etc/sysctl.conf">
              <div className="p-3">
                <PreBlock content={data.sysctl_conf as string} maxHeight="300px" />
              </div>
            </Section>

            {/* 11. /etc/passwd */}
            <Section icon={Users} title="/etc/passwd">
              <div className="p-3">
                <PreBlock content={data.etc_passwd as string} maxHeight="300px" />
              </div>
            </Section>

            {/* 12. /etc/hosts */}
            <Section icon={Server} title="/etc/hosts">
              <div className="p-3">
                <PreBlock content={data.etc_hosts as string} maxHeight="200px" />
              </div>
            </Section>

            <Separator />
          </div>
        )}
      </SheetContent>
    </Sheet>
  )
}
