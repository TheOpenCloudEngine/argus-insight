"use client"

import { useCallback, useEffect, useState } from "react"
import { Cpu, HardDrive, Loader2, Pencil, Plus, Star, Trash2 } from "lucide-react"

import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@workspace/ui/components/card"
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@workspace/ui/components/table"
import { Checkbox } from "@workspace/ui/components/checkbox"

import type { ResourceProfile } from "@/features/workspaces/types"
import {
  createResourceProfile,
  deleteResourceProfile,
  fetchResourceProfiles,
  updateResourceProfile,
} from "@/features/workspaces/api"

interface ProfileFormData {
  name: string
  display_name: string
  description: string
  cpu_cores: string
  memory_gb: string
  is_default: boolean
}

const emptyForm: ProfileFormData = {
  name: "",
  display_name: "",
  description: "",
  cpu_cores: "",
  memory_gb: "",
  is_default: false,
}

export function ResourceProfiles() {
  const [profiles, setProfiles] = useState<ResourceProfile[]>([])
  const [loading, setLoading] = useState(true)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [form, setForm] = useState<ProfileFormData>(emptyForm)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setLoading(true)
      const data = await fetchResourceProfiles()
      setProfiles(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load profiles")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const openCreate = () => {
    setEditingId(null)
    setForm(emptyForm)
    setDialogOpen(true)
  }

  const openEdit = (p: ResourceProfile) => {
    setEditingId(p.id)
    setForm({
      name: p.name,
      display_name: p.display_name,
      description: p.description || "",
      cpu_cores: String(p.cpu_cores),
      memory_gb: String(p.memory_gb),
      is_default: p.is_default,
    })
    setDialogOpen(true)
  }

  const handleSave = async () => {
    setSaving(true)
    setError(null)
    try {
      const cpu = parseFloat(form.cpu_cores)
      const mem = parseFloat(form.memory_gb)
      if (isNaN(cpu) || cpu <= 0 || isNaN(mem) || mem <= 0) {
        setError("CPU and Memory must be positive numbers")
        return
      }

      if (editingId) {
        await updateResourceProfile(editingId, {
          display_name: form.display_name,
          description: form.description || undefined,
          cpu_cores: cpu,
          memory_gb: mem,
          is_default: form.is_default,
        })
      } else {
        await createResourceProfile({
          name: form.name,
          display_name: form.display_name,
          description: form.description || undefined,
          cpu_cores: cpu,
          memory_gb: mem,
          is_default: form.is_default,
        })
      }
      setDialogOpen(false)
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save profile")
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm("Are you sure you want to delete this profile?")) return
    try {
      await deleteResourceProfile(id)
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete profile")
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-lg">Resource Profiles</CardTitle>
            <CardDescription>
              Workspace resource quota profiles. Define CPU/Memory limits per workspace.
            </CardDescription>
          </div>
          <Button size="sm" onClick={openCreate}>
            <Plus className="mr-1.5 h-3.5 w-3.5" />
            Add Profile
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {error && (
          <div className="mb-4 rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
            {error}
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        ) : profiles.length === 0 ? (
          <div className="py-8 text-center text-sm text-muted-foreground">
            No profiles defined yet. Create one to set workspace resource limits.
          </div>
        ) : (
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[180px]">Name</TableHead>
                  <TableHead>Description</TableHead>
                  <TableHead className="w-[120px] text-right">CPU (Cores)</TableHead>
                  <TableHead className="w-[120px] text-right">Memory (GB)</TableHead>
                  <TableHead className="w-[100px] text-center">Default</TableHead>
                  <TableHead className="w-[100px]" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {profiles.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell className="font-medium">{p.display_name}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {p.description || "-"}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <Cpu className="h-3.5 w-3.5 text-muted-foreground" />
                        {p.cpu_cores}
                      </div>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <HardDrive className="h-3.5 w-3.5 text-muted-foreground" />
                        {p.memory_gb}
                      </div>
                    </TableCell>
                    <TableCell className="text-center">
                      {p.is_default && (
                        <Badge variant="secondary" className="gap-1">
                          <Star className="h-3 w-3" />
                          Default
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7"
                          onClick={() => openEdit(p)}
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 text-destructive hover:text-destructive"
                          onClick={() => handleDelete(p.id)}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}

        {/* Create / Edit Dialog */}
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>{editingId ? "Edit Profile" : "Create Profile"}</DialogTitle>
              <DialogDescription>
                Define CPU and memory limits for this resource profile.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-2">
              {!editingId && (
                <div className="space-y-1.5">
                  <Label htmlFor="profile-name">Name (slug)</Label>
                  <Input
                    id="profile-name"
                    placeholder="e.g. small, medium, large"
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                  />
                </div>
              )}
              <div className="space-y-1.5">
                <Label htmlFor="profile-display">Display Name</Label>
                <Input
                  id="profile-display"
                  placeholder="e.g. Small, Medium, Large"
                  value={form.display_name}
                  onChange={(e) => setForm({ ...form, display_name: e.target.value })}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="profile-desc">Description</Label>
                <Input
                  id="profile-desc"
                  placeholder="Optional description"
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <Label htmlFor="profile-cpu">CPU Cores</Label>
                  <Input
                    id="profile-cpu"
                    type="number"
                    min="0"
                    step="0.5"
                    placeholder="e.g. 8"
                    value={form.cpu_cores}
                    onChange={(e) => setForm({ ...form, cpu_cores: e.target.value })}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="profile-mem">Memory (GB)</Label>
                  <Input
                    id="profile-mem"
                    type="number"
                    min="0"
                    step="0.5"
                    placeholder="e.g. 16"
                    value={form.memory_gb}
                    onChange={(e) => setForm({ ...form, memory_gb: e.target.value })}
                  />
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Checkbox
                  id="profile-default"
                  checked={form.is_default}
                  onCheckedChange={(checked) =>
                    setForm({ ...form, is_default: checked === true })
                  }
                />
                <Label htmlFor="profile-default" className="text-sm font-normal">
                  Set as default profile for new workspaces
                </Label>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setDialogOpen(false)}>
                Cancel
              </Button>
              <Button onClick={handleSave} disabled={saving}>
                {saving && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
                {editingId ? "Update" : "Create"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </CardContent>
    </Card>
  )
}
