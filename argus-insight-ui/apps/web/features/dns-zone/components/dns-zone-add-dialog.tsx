/**
 * Add DNS Record Dialog.
 *
 * Renders a form dialog for adding a new DNS record.
 * The form fields change based on the selected record type.
 */

"use client"

import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"
import { zodResolver } from "@hookform/resolvers/zod"
import { Loader2 } from "lucide-react"

import { Button } from "@workspace/ui/components/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@workspace/ui/components/form"
import { Input } from "@workspace/ui/components/input"
import { updateZoneRecords } from "../api"
import { useDnsZone } from "./dns-zone-provider"

// --------------------------------------------------------------------------- //
// Schema
// --------------------------------------------------------------------------- //

const baseSchema = z.object({
  name: z.string().min(1, "Name is required"),
  ttl: z.coerce.number().int().min(1).default(3600),
})

const aSchema = baseSchema.extend({ address: z.string().min(1, "IP address is required") })
const aaaaSchema = baseSchema.extend({ address: z.string().min(1, "IPv6 address is required") })
const cnameSchema = baseSchema.extend({ target: z.string().min(1, "Target is required") })
const mxSchema = baseSchema.extend({
  priority: z.coerce.number().int().min(0).default(10),
  server: z.string().min(1, "Mail server is required"),
})
const txtSchema = baseSchema.extend({ text: z.string().min(1, "Text value is required") })
const nsSchema = baseSchema.extend({ nameserver: z.string().min(1, "Nameserver is required") })
const ptrSchema = baseSchema.extend({ pointer: z.string().min(1, "Pointer is required") })
const srvSchema = baseSchema.extend({
  priority: z.coerce.number().int().min(0).default(10),
  weight: z.coerce.number().int().min(0).default(0),
  port: z.coerce.number().int().min(1).max(65535),
  target: z.string().min(1, "Target is required"),
})

// --------------------------------------------------------------------------- //
// Helpers
// --------------------------------------------------------------------------- //

/** Ensure a DNS name has a trailing dot. */
function ensureDot(name: string): string {
  const trimmed = name.trim()
  return trimmed.endsWith(".") ? trimmed : `${trimmed}.`
}

/** Build the content string for a record based on its type. */
function buildContent(type: string, values: Record<string, unknown>): string {
  switch (type) {
    case "A":
    case "AAAA":
      return String(values.address)
    case "CNAME":
      return ensureDot(String(values.target))
    case "MX":
      return `${values.priority} ${ensureDot(String(values.server))}`
    case "TXT":
      // TXT records need to be quoted
      return `"${String(values.text)}"`
    case "NS":
      return ensureDot(String(values.nameserver))
    case "PTR":
      return ensureDot(String(values.pointer))
    case "SRV":
      return `${values.priority} ${values.weight} ${values.port} ${ensureDot(String(values.target))}`
    default:
      return String(values.address ?? values.target ?? "")
  }
}

function getSchema(type: string) {
  switch (type) {
    case "A": return aSchema
    case "AAAA": return aaaaSchema
    case "CNAME": return cnameSchema
    case "MX": return mxSchema
    case "TXT": return txtSchema
    case "NS": return nsSchema
    case "PTR": return ptrSchema
    case "SRV": return srvSchema
    default: return aSchema
  }
}

// --------------------------------------------------------------------------- //
// Component
// --------------------------------------------------------------------------- //

type DnsZoneAddDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  recordType: string
}

export function DnsZoneAddDialog({ open, onOpenChange, recordType }: DnsZoneAddDialogProps) {
  const { zone, refreshRecords } = useDnsZone()
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const schema = getSchema(recordType)
  const form = useForm({
    resolver: zodResolver(schema),
    defaultValues: {
      name: zone ? `${zone}.` : "",
      ttl: 3600,
      address: "",
      target: "",
      priority: 10,
      server: "",
      text: "",
      nameserver: "",
      pointer: "",
      weight: 0,
      port: 443,
    },
  })

  async function onSubmit(values: Record<string, unknown>) {
    setSaving(true)
    setError(null)
    try {
      const name = ensureDot(String(values.name))
      const content = buildContent(recordType, values)
      const ttl = Number(values.ttl) || 3600

      await updateZoneRecords([
        {
          name,
          type: recordType,
          ttl,
          changetype: "REPLACE",
          records: [{ content, disabled: false }],
        },
      ])

      onOpenChange(false)
      form.reset()
      await refreshRecords()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add record")
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle>Add {recordType} Record</DialogTitle>
          <DialogDescription>
            Add a new {recordType} record to zone &apos;{zone}&apos;
          </DialogDescription>
        </DialogHeader>

        {error && (
          <div className="rounded-md bg-red-50 px-4 py-2 text-sm text-red-800 dark:bg-red-950 dark:text-red-200">
            {error}
          </div>
        )}

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            {/* Common: Name */}
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Name <span className="text-destructive">*</span></FormLabel>
                  <FormControl>
                    <Input placeholder={`e.g. www.${zone}`} {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Common: TTL */}
            <FormField
              control={form.control}
              name="ttl"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>TTL</FormLabel>
                  <FormControl>
                    <Input type="number" min={1} placeholder="3600" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Type-specific fields */}
            {(recordType === "A" || recordType === "AAAA") && (
              <FormField
                control={form.control}
                name="address"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      {recordType === "A" ? "IP Address" : "IPv6 Address"}{" "}
                      <span className="text-destructive">*</span>
                    </FormLabel>
                    <FormControl>
                      <Input
                        placeholder={recordType === "A" ? "e.g. 10.0.1.50" : "e.g. 2001:db8::1"}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            )}

            {recordType === "CNAME" && (
              <FormField
                control={form.control}
                name="target"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Target <span className="text-destructive">*</span></FormLabel>
                    <FormControl>
                      <Input placeholder="e.g. www.example.com" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            )}

            {recordType === "MX" && (
              <>
                <FormField
                  control={form.control}
                  name="priority"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Priority</FormLabel>
                      <FormControl>
                        <Input type="number" min={0} placeholder="10" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="server"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Mail Server <span className="text-destructive">*</span></FormLabel>
                      <FormControl>
                        <Input placeholder="e.g. mail.example.com" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </>
            )}

            {recordType === "TXT" && (
              <FormField
                control={form.control}
                name="text"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Text Value <span className="text-destructive">*</span></FormLabel>
                    <FormControl>
                      <Input placeholder='e.g. v=spf1 include:_spf.google.com ~all' {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            )}

            {recordType === "NS" && (
              <FormField
                control={form.control}
                name="nameserver"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Nameserver <span className="text-destructive">*</span></FormLabel>
                    <FormControl>
                      <Input placeholder="e.g. ns1.example.com" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            )}

            {recordType === "PTR" && (
              <FormField
                control={form.control}
                name="pointer"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Pointer <span className="text-destructive">*</span></FormLabel>
                    <FormControl>
                      <Input placeholder="e.g. host.example.com" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            )}

            {recordType === "SRV" && (
              <>
                <div className="grid grid-cols-3 gap-3">
                  <FormField
                    control={form.control}
                    name="priority"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Priority</FormLabel>
                        <FormControl>
                          <Input type="number" min={0} placeholder="10" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="weight"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Weight</FormLabel>
                        <FormControl>
                          <Input type="number" min={0} placeholder="0" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="port"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Port <span className="text-destructive">*</span></FormLabel>
                        <FormControl>
                          <Input type="number" min={1} max={65535} placeholder="443" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
                <FormField
                  control={form.control}
                  name="target"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Target <span className="text-destructive">*</span></FormLabel>
                      <FormControl>
                        <Input placeholder="e.g. svc.example.com" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </>
            )}

            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={saving}>
                {saving && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />}
                OK
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
