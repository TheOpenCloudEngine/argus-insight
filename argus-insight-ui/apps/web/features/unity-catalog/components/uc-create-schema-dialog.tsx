"use client"

import { useCallback, useEffect, useState } from "react"
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
import { createSchema } from "../api"

const NAME_PATTERN = /^[a-z_]+$/

const schema = z.object({
  name: z
    .string()
    .min(1, "Name is required")
    .regex(NAME_PATTERN, "Only lowercase letters and underscores are allowed"),
  comment: z.string().optional(),
})

type Props = {
  open: boolean
  onOpenChange: (open: boolean) => void
  catalogName: string
  onSuccess: () => void
}

export function CreateSchemaDialog({ open, onOpenChange, catalogName, onSuccess }: Props) {
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [nameValid, setNameValid] = useState(false)

  const form = useForm({
    resolver: zodResolver(schema),
    defaultValues: { name: "", comment: "" },
    mode: "onChange",
  })

  const nameValue = form.watch("name")

  // Debounce validation: validate 1 second after user stops typing
  useEffect(() => {
    setNameValid(false)
    if (!nameValue) return

    const timer = setTimeout(() => {
      const valid = NAME_PATTERN.test(nameValue)
      setNameValid(valid)
      if (!valid) {
        form.trigger("name")
      }
    }, 1000)

    return () => clearTimeout(timer)
  }, [nameValue, form])

  function handleOpenChange(next: boolean) {
    if (!next) {
      form.reset()
      setError(null)
      setNameValid(false)
    }
    onOpenChange(next)
  }

  async function onSubmit(values: z.infer<typeof schema>) {
    setSaving(true)
    setError(null)
    try {
      await createSchema({ catalog_name: catalogName, ...values })
      handleOpenChange(false)
      onSuccess()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create schema")
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle>Create Schema</DialogTitle>
          <DialogDescription>Create a new schema in catalog &apos;{catalogName}&apos;.</DialogDescription>
        </DialogHeader>
        {error && (
          <div className="rounded-md bg-red-50 px-4 py-2 text-sm text-red-800 dark:bg-red-950 dark:text-red-200">{error}</div>
        )}
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField control={form.control} name="name" render={({ field }) => (
              <FormItem>
                <FormLabel>Name <span className="text-destructive">*</span></FormLabel>
                <FormControl><Input placeholder="e.g. analytics" {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
            <FormField control={form.control} name="comment" render={({ field }) => (
              <FormItem>
                <FormLabel>Description</FormLabel>
                <FormControl><Input placeholder="Optional description" {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => handleOpenChange(false)}>Cancel</Button>
              <Button type="submit" disabled={saving || !nameValid}>
                {saving && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />}
                Create
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
