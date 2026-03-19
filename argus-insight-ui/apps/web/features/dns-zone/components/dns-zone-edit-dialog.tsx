/**
 * Edit DNS Record Dialog.
 *
 * Provides a simplified edit form that allows modifying the name, TTL,
 * and content (data) of an existing DNS record. Unlike the Add dialog,
 * which has type-specific fields, the Edit dialog uses a single raw
 * content field because the user is editing an existing record whose
 * content format is already established.
 *
 * The form is pre-populated with the current record values. On submit,
 * it sends a REPLACE changetype patch to the PowerDNS API, preserving
 * the record's current enabled/disabled status.
 *
 * Note: Editing a record's name effectively moves it to a different RRset
 * in PowerDNS. The old RRset may need manual cleanup if it becomes empty.
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
import { type DnsRecord } from "../data/schema"
import { useDnsZone } from "./dns-zone-provider"

/** Zod validation schema for the edit form (simpler than add, just raw content). */
const editSchema = z.object({
  name: z.string().min(1, "Name is required"),
  ttl: z.coerce.number().int().min(1).default(3600),
  content: z.string().min(1, "Data is required"),
})

/** Ensure a DNS name has a trailing dot (FQDN format required by PowerDNS). */
function ensureDot(name: string): string {
  const trimmed = name.trim()
  return trimmed.endsWith(".") ? trimmed : `${trimmed}.`
}

/** Props for the DnsZoneEditDialog component. */
type DnsZoneEditDialogProps = {
  /** Whether the dialog is open */
  open: boolean
  /** Callback to open/close the dialog */
  onOpenChange: (open: boolean) => void
  /** The record being edited (provides initial form values and record type) */
  currentRow: DnsRecord
}

/**
 * Modal dialog for editing an existing DNS record.
 *
 * Shows a form pre-filled with the record's current name, TTL, and content.
 * The record type is displayed in the title but cannot be changed.
 * On submit, sends a REPLACE patch preserving the current disabled status.
 */
export function DnsZoneEditDialog({ open, onOpenChange, currentRow }: DnsZoneEditDialogProps) {
  const { refreshRecords } = useDnsZone()
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const form = useForm({
    resolver: zodResolver(editSchema),
    defaultValues: {
      name: currentRow.name,
      ttl: currentRow.ttl,
      content: currentRow.content,
    },
  })

  /**
   * Form submit handler.
   * Sends a REPLACE patch with the updated values, preserving the record's
   * current disabled/enabled status. Closes the dialog and refreshes on success.
   */
  async function onSubmit(values: z.infer<typeof editSchema>) {
    setSaving(true)
    setError(null)
    try {
      const name = ensureDot(values.name)

      await updateZoneRecords([
        {
          name,
          type: currentRow.type,
          ttl: values.ttl,
          changetype: "REPLACE",
          records: [{ content: values.content, disabled: currentRow.disabled }],
        },
      ])

      onOpenChange(false)
      await refreshRecords()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update record")
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle>Edit {currentRow.type} Record</DialogTitle>
          <DialogDescription>
            Modify the {currentRow.type} record for {currentRow.name}
          </DialogDescription>
        </DialogHeader>

        {error && (
          <div className="rounded-md bg-red-50 px-4 py-2 text-sm text-red-800 dark:bg-red-950 dark:text-red-200">
            {error}
          </div>
        )}

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Name <span className="text-destructive">*</span></FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="ttl"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>TTL</FormLabel>
                  <FormControl>
                    <Input type="number" min={1} {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="content"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Data <span className="text-destructive">*</span></FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

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
