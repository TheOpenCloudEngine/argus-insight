"use client"

import React, { useCallback, useState } from "react"
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
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"
import * as api from "../api"
import { useSql } from "./sql-provider"

export function SaveQueryDialog() {
  const { dialog, setDialog, tabs, activeTabId } = useSql()
  const activeTab = tabs.find((t) => t.id === activeTabId)

  const [name, setName] = useState("")
  const [folder, setFolder] = useState("")
  const [description, setDescription] = useState("")
  const [saving, setSaving] = useState(false)

  const isOpen = dialog === "save-query"

  const handleClose = useCallback(() => {
    setDialog(null)
    setName("")
    setFolder("")
    setDescription("")
  }, [setDialog])

  const handleSave = useCallback(async () => {
    if (!activeTab?.datasourceId || !activeTab?.sql.trim() || !name.trim()) return
    setSaving(true)
    try {
      await api.createSavedQuery({
        name: name.trim(),
        folder: folder.trim(),
        datasource_id: activeTab.datasourceId,
        sql_text: activeTab.sql,
        description: description.trim(),
      })
      handleClose()
    } catch (e) {
      console.error("Failed to save query", e)
    } finally {
      setSaving(false)
    }
  }, [activeTab, name, folder, description, handleClose])

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && handleClose()}>
      <DialogContent className="sm:max-w-[400px]">
        <DialogHeader>
          <DialogTitle>Save Query</DialogTitle>
          <DialogDescription>Save this query for later use.</DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-2">
          <div className="grid gap-1.5">
            <Label htmlFor="sq-name">Name</Label>
            <Input
              id="sq-name"
              placeholder="My Query"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="sq-folder">Folder (optional)</Label>
            <Input
              id="sq-folder"
              placeholder="reports"
              value={folder}
              onChange={(e) => setFolder(e.target.value)}
            />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="sq-desc">Description (optional)</Label>
            <Input
              id="sq-desc"
              placeholder="Description..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={saving || !name.trim()}>
            {saving ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : null}
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
