"use client"

import { useCallback, useEffect, useState } from "react"
import { CheckCircle2, Loader2, Plus, Trash2 } from "lucide-react"
import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import { Card, CardContent, CardHeader, CardTitle } from "@workspace/ui/components/card"
import { Checkbox } from "@workspace/ui/components/checkbox"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"
import { authFetch } from "@/features/auth/auth-fetch"

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface AptRepo {
  type: string
  url: string
  dist: string
  components: string
  enabled: boolean
  trusted: boolean
}

interface YumRepo {
  repo_id: string
  name: string
  baseurl: string
  gpgcheck: boolean
  enabled: boolean
  gpgkey?: string
}

interface ApkRepo {
  url: string
  enabled: boolean
}

interface OsRepos {
  label: string
  builtin: Record<string, unknown>[]
  custom: Record<string, unknown>[]
}

type AllRepos = Record<string, OsRepos>

/* ------------------------------------------------------------------ */
/*  APT Section                                                        */
/* ------------------------------------------------------------------ */

function AptSection({
  repos,
  onUpdate,
  saving,
  saved,
  onSave,
}: {
  repos: OsRepos
  onUpdate: (repos: OsRepos) => void
  saving: boolean
  saved: boolean
  onSave: () => void
}) {
  const [addOpen, setAddOpen] = useState(false)
  const [form, setForm] = useState<AptRepo>({
    type: "deb", url: "", dist: "", components: "main", enabled: true, trusted: true,
  })

  const toggleBuiltin = (idx: number) => {
    const updated = [...repos.builtin]
    updated[idx] = { ...updated[idx], enabled: !updated[idx].enabled }
    onUpdate({ ...repos, builtin: updated })
  }

  const toggleCustom = (idx: number) => {
    const updated = [...repos.custom]
    updated[idx] = { ...updated[idx], enabled: !updated[idx].enabled }
    onUpdate({ ...repos, custom: updated })
  }

  const removeCustom = (idx: number) => {
    onUpdate({ ...repos, custom: repos.custom.filter((_, i) => i !== idx) })
  }

  const handleAdd = () => {
    if (!form.url || !form.dist) return
    onUpdate({ ...repos, custom: [...repos.custom, { ...form }] })
    setAddOpen(false)
    setForm({ type: "deb", url: "", dist: "", components: "main", enabled: true, trusted: false })
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-3">
        <CardTitle className="text-sm">Debian/Ubuntu (APT)</CardTitle>
        <Button variant="outline" size="sm" className="text-xs" onClick={() => setAddOpen(true)}>
          <Plus className="mr-1.5 h-3.5 w-3.5" />
          Add Repo
        </Button>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Built-in */}
        <div>
          <p className="text-xs font-medium text-muted-foreground mb-2">Built-in</p>
          <div className="space-y-1.5">
            {(repos.builtin as AptRepo[]).map((r, i) => (
              <div key={i} className="flex items-center gap-2 text-sm rounded px-2 py-1">
                <Checkbox checked={r.enabled} onCheckedChange={() => toggleBuiltin(i)} />
                <Badge variant="outline" className="text-[10px] font-mono shrink-0">{r.type}</Badge>
                <Input
                  className="h-7 text-xs font-mono flex-1"
                  value={r.url}
                  onChange={(e) => {
                    const updated = [...repos.builtin] as AptRepo[]
                    updated[i] = { ...updated[i], url: e.target.value }
                    onUpdate({ ...repos, builtin: updated })
                  }}
                />
                <Input
                  className="h-7 text-xs font-mono w-28"
                  value={r.dist}
                  onChange={(e) => {
                    const updated = [...repos.builtin] as AptRepo[]
                    updated[i] = { ...updated[i], dist: e.target.value }
                    onUpdate({ ...repos, builtin: updated })
                  }}
                />
                <Input
                  className="h-7 text-xs font-mono w-36"
                  value={r.components}
                  onChange={(e) => {
                    const updated = [...repos.builtin] as AptRepo[]
                    updated[i] = { ...updated[i], components: e.target.value }
                    onUpdate({ ...repos, builtin: updated })
                  }}
                />
              </div>
            ))}
          </div>
        </div>

        {/* Custom */}
        <div>
          <p className="text-xs font-medium text-muted-foreground mb-2">Custom</p>
          {repos.custom.length === 0 ? (
            <p className="text-xs text-muted-foreground px-2">No custom repositories.</p>
          ) : (
            <div className="space-y-1.5">
              {(repos.custom as AptRepo[]).map((r, i) => (
                <div key={i} className="flex items-center gap-2 text-sm rounded px-2 py-1 hover:bg-muted/50">
                  <Checkbox checked={r.enabled} onCheckedChange={() => toggleCustom(i)} />
                  <Badge variant="outline" className="text-[10px] font-mono">{r.type}</Badge>
                  <span className="truncate font-mono text-xs flex-1">{r.url} {r.dist} {r.components}</span>
                  {r.trusted && <Badge variant="secondary" className="text-[10px]">trusted</Badge>}
                  <Button variant="ghost" size="icon" className="h-6 w-6 text-red-500" onClick={() => removeCustom(i)}>
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-2">
          {saved && <span className="flex items-center gap-1 text-xs text-green-600"><CheckCircle2 className="h-3 w-3" />Saved</span>}
          <Button size="sm" className="text-xs" onClick={onSave} disabled={saving}>
            {saving && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}Save
          </Button>
        </div>
      </CardContent>

      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Add APT Repository</DialogTitle>
            <DialogDescription>Add a custom Debian/Ubuntu package repository.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="grid grid-cols-4 gap-2">
              <div>
                <Label className="text-xs">Type</Label>
                <Select value={form.type} onValueChange={(v) => setForm({ ...form, type: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="deb">deb</SelectItem>
                    <SelectItem value="deb-src">deb-src</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="col-span-3">
                <Label className="text-xs">URL</Label>
                <Input value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} placeholder="http://10.0.1.50:8081/repository/apt-public/" />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <Label className="text-xs">Distribution</Label>
                <Input value={form.dist} onChange={(e) => setForm({ ...form, dist: e.target.value })} placeholder="bookworm" />
              </div>
              <div>
                <Label className="text-xs">Components</Label>
                <Input value={form.components} onChange={(e) => setForm({ ...form, components: e.target.value })} placeholder="main" />
              </div>
            </div>
            <label className="flex items-center gap-2 text-sm">
              <Checkbox checked={form.trusted} onCheckedChange={(v) => setForm({ ...form, trusted: !!v })} />
              Trusted (skip GPG verification)
            </label>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" size="sm" onClick={() => setAddOpen(false)}>Cancel</Button>
            <Button size="sm" onClick={handleAdd} disabled={!form.url || !form.dist}>Add</Button>
          </div>
        </DialogContent>
      </Dialog>
    </Card>
  )
}

/* ------------------------------------------------------------------ */
/*  YUM Section                                                        */
/* ------------------------------------------------------------------ */

function YumSection({
  repos,
  onUpdate,
  saving,
  saved,
  onSave,
}: {
  repos: OsRepos
  onUpdate: (repos: OsRepos) => void
  saving: boolean
  saved: boolean
  onSave: () => void
}) {
  const [addOpen, setAddOpen] = useState(false)
  const [form, setForm] = useState<YumRepo>({
    repo_id: "", name: "", baseurl: "", gpgcheck: false, enabled: true,
  })

  const toggleBuiltin = (idx: number) => {
    const updated = [...repos.builtin]
    updated[idx] = { ...updated[idx], enabled: !updated[idx].enabled }
    onUpdate({ ...repos, builtin: updated })
  }

  const toggleCustom = (idx: number) => {
    const updated = [...repos.custom]
    updated[idx] = { ...updated[idx], enabled: !updated[idx].enabled }
    onUpdate({ ...repos, custom: updated })
  }

  const removeCustom = (idx: number) => {
    onUpdate({ ...repos, custom: repos.custom.filter((_, i) => i !== idx) })
  }

  const handleAdd = () => {
    if (!form.repo_id || !form.baseurl) return
    onUpdate({ ...repos, custom: [...repos.custom, { ...form }] })
    setAddOpen(false)
    setForm({ repo_id: "", name: "", baseurl: "", gpgcheck: false, enabled: true })
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-3">
        <CardTitle className="text-sm">RHEL/CentOS (YUM)</CardTitle>
        <Button variant="outline" size="sm" className="text-xs" onClick={() => setAddOpen(true)}>
          <Plus className="mr-1.5 h-3.5 w-3.5" />
          Add Repo
        </Button>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <p className="text-xs font-medium text-muted-foreground mb-2">Built-in</p>
          <div className="space-y-1.5">
            {(repos.builtin as YumRepo[]).map((r, i) => (
              <div key={i} className="flex items-center gap-2 text-sm rounded px-2 py-1">
                <Checkbox checked={r.enabled} onCheckedChange={() => toggleBuiltin(i)} />
                <Badge variant="outline" className="text-[10px] font-mono shrink-0">[{r.repo_id}]</Badge>
                <Input
                  className="h-7 text-xs w-40"
                  value={r.name}
                  onChange={(e) => {
                    const updated = [...repos.builtin] as YumRepo[]
                    updated[i] = { ...updated[i], name: e.target.value }
                    onUpdate({ ...repos, builtin: updated })
                  }}
                />
                <Input
                  className="h-7 text-xs font-mono flex-1"
                  value={r.baseurl}
                  onChange={(e) => {
                    const updated = [...repos.builtin] as YumRepo[]
                    updated[i] = { ...updated[i], baseurl: e.target.value }
                    onUpdate({ ...repos, builtin: updated })
                  }}
                />
              </div>
            ))}
          </div>
        </div>

        <div>
          <p className="text-xs font-medium text-muted-foreground mb-2">Custom</p>
          {repos.custom.length === 0 ? (
            <p className="text-xs text-muted-foreground px-2">No custom repositories.</p>
          ) : (
            <div className="space-y-1.5">
              {(repos.custom as YumRepo[]).map((r, i) => (
                <div key={i} className="flex items-center gap-2 text-sm rounded px-2 py-1 hover:bg-muted/50">
                  <Checkbox checked={r.enabled} onCheckedChange={() => toggleCustom(i)} />
                  <Badge variant="outline" className="text-[10px] font-mono">[{r.repo_id}]</Badge>
                  <span className="truncate text-xs flex-1">{r.name}</span>
                  <span className="truncate font-mono text-[10px] text-muted-foreground max-w-[200px]">{r.baseurl}</span>
                  {!r.gpgcheck && <Badge variant="secondary" className="text-[10px]">no-gpg</Badge>}
                  <Button variant="ghost" size="icon" className="h-6 w-6 text-red-500" onClick={() => removeCustom(i)}>
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-2">
          {saved && <span className="flex items-center gap-1 text-xs text-green-600"><CheckCircle2 className="h-3 w-3" />Saved</span>}
          <Button size="sm" className="text-xs" onClick={onSave} disabled={saving}>
            {saving && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}Save
          </Button>
        </div>
      </CardContent>

      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Add YUM Repository</DialogTitle>
            <DialogDescription>Add a custom RHEL/CentOS package repository.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-2">
              <div>
                <Label className="text-xs">Repo ID</Label>
                <Input value={form.repo_id} onChange={(e) => setForm({ ...form, repo_id: e.target.value })} placeholder="argus-custom" />
              </div>
              <div>
                <Label className="text-xs">Name</Label>
                <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Argus Custom Repo" />
              </div>
            </div>
            <div>
              <Label className="text-xs">Base URL</Label>
              <Input value={form.baseurl} onChange={(e) => setForm({ ...form, baseurl: e.target.value })} placeholder="http://10.0.1.50:8081/repository/yum-public/" />
            </div>
            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2 text-sm">
                <Checkbox checked={form.gpgcheck} onCheckedChange={(v) => setForm({ ...form, gpgcheck: !!v })} />
                GPG Check
              </label>
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" size="sm" onClick={() => setAddOpen(false)}>Cancel</Button>
            <Button size="sm" onClick={handleAdd} disabled={!form.repo_id || !form.baseurl}>Add</Button>
          </div>
        </DialogContent>
      </Dialog>
    </Card>
  )
}

/* ------------------------------------------------------------------ */
/*  APK Section                                                        */
/* ------------------------------------------------------------------ */

function ApkSection({
  repos,
  onUpdate,
  saving,
  saved,
  onSave,
}: {
  repos: OsRepos
  onUpdate: (repos: OsRepos) => void
  saving: boolean
  saved: boolean
  onSave: () => void
}) {
  const [addOpen, setAddOpen] = useState(false)
  const [newUrl, setNewUrl] = useState("")

  const toggleBuiltin = (idx: number) => {
    const updated = [...repos.builtin]
    updated[idx] = { ...updated[idx], enabled: !updated[idx].enabled }
    onUpdate({ ...repos, builtin: updated })
  }

  const toggleCustom = (idx: number) => {
    const updated = [...repos.custom]
    updated[idx] = { ...updated[idx], enabled: !updated[idx].enabled }
    onUpdate({ ...repos, custom: updated })
  }

  const removeCustom = (idx: number) => {
    onUpdate({ ...repos, custom: repos.custom.filter((_, i) => i !== idx) })
  }

  const handleAdd = () => {
    if (!newUrl) return
    onUpdate({ ...repos, custom: [...repos.custom, { url: newUrl, enabled: true }] })
    setAddOpen(false)
    setNewUrl("")
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-3">
        <CardTitle className="text-sm">Alpine (APK)</CardTitle>
        <Button variant="outline" size="sm" className="text-xs" onClick={() => setAddOpen(true)}>
          <Plus className="mr-1.5 h-3.5 w-3.5" />
          Add Repo
        </Button>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <p className="text-xs font-medium text-muted-foreground mb-2">Built-in</p>
          <div className="space-y-1.5">
            {(repos.builtin as ApkRepo[]).map((r, i) => (
              <div key={i} className="flex items-center gap-2 text-sm rounded px-2 py-1">
                <Checkbox checked={r.enabled} onCheckedChange={() => toggleBuiltin(i)} />
                <Input
                  className="h-7 text-xs font-mono flex-1"
                  value={r.url}
                  onChange={(e) => {
                    const updated = [...repos.builtin] as ApkRepo[]
                    updated[i] = { ...updated[i], url: e.target.value }
                    onUpdate({ ...repos, builtin: updated })
                  }}
                />
              </div>
            ))}
          </div>
        </div>

        <div>
          <p className="text-xs font-medium text-muted-foreground mb-2">Custom</p>
          {repos.custom.length === 0 ? (
            <p className="text-xs text-muted-foreground px-2">No custom repositories.</p>
          ) : (
            <div className="space-y-1.5">
              {(repos.custom as ApkRepo[]).map((r, i) => (
                <div key={i} className="flex items-center gap-2 text-sm rounded px-2 py-1 hover:bg-muted/50">
                  <Checkbox checked={r.enabled} onCheckedChange={() => toggleCustom(i)} />
                  <span className="truncate font-mono text-xs flex-1">{r.url}</span>
                  <Button variant="ghost" size="icon" className="h-6 w-6 text-red-500" onClick={() => removeCustom(i)}>
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-2">
          {saved && <span className="flex items-center gap-1 text-xs text-green-600"><CheckCircle2 className="h-3 w-3" />Saved</span>}
          <Button size="sm" className="text-xs" onClick={onSave} disabled={saving}>
            {saving && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}Save
          </Button>
        </div>
      </CardContent>

      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Add APK Repository</DialogTitle>
            <DialogDescription>Add a custom Alpine package repository URL.</DialogDescription>
          </DialogHeader>
          <div>
            <Label className="text-xs">Repository URL</Label>
            <Input value={newUrl} onChange={(e) => setNewUrl(e.target.value)} placeholder="http://10.0.1.50:8081/repository/apk-public/v3.21/main" />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" size="sm" onClick={() => setAddOpen(false)}>Cancel</Button>
            <Button size="sm" onClick={handleAdd} disabled={!newUrl}>Add</Button>
          </div>
        </DialogContent>
      </Dialog>
    </Card>
  )
}

/* ------------------------------------------------------------------ */
/*  Main Component                                                     */
/* ------------------------------------------------------------------ */

export function RepositoriesSettings() {
  const [allRepos, setAllRepos] = useState<AllRepos>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState<Record<string, boolean>>({})
  const [saved, setSaved] = useState<Record<string, boolean>>({})

  const loadConfig = useCallback(async () => {
    try {
      const res = await authFetch("/api/v1/settings/repositories")
      if (res.ok) setAllRepos(await res.json())
    } catch { /* ignore */ }
    setLoading(false)
  }, [])

  useEffect(() => { loadConfig() }, [loadConfig])

  const handleUpdate = (osType: string, repos: OsRepos) => {
    setAllRepos((prev) => ({ ...prev, [osType]: repos }))
    setSaved((prev) => ({ ...prev, [osType]: false }))
  }

  const handleSave = async (osType: string) => {
    const repos = allRepos[osType]
    if (!repos) return
    setSaving((prev) => ({ ...prev, [osType]: true }))
    try {
      const res = await authFetch(`/api/v1/settings/repositories/${osType}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ builtin: repos.builtin, custom: repos.custom }),
      })
      if (res.ok) {
        setSaved((prev) => ({ ...prev, [osType]: true }))
        setTimeout(() => setSaved((prev) => ({ ...prev, [osType]: false })), 2000)
      }
    } catch { /* ignore */ }
    setSaving((prev) => ({ ...prev, [osType]: false }))
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Configure OS-level package repositories. These are injected into service containers during deployment.
      </p>

      {allRepos.apt && (
        <AptSection
          repos={allRepos.apt}
          onUpdate={(r) => handleUpdate("apt", r)}
          saving={saving.apt ?? false}
          saved={saved.apt ?? false}
          onSave={() => handleSave("apt")}
        />
      )}

      {allRepos.yum && (
        <YumSection
          repos={allRepos.yum}
          onUpdate={(r) => handleUpdate("yum", r)}
          saving={saving.yum ?? false}
          saved={saved.yum ?? false}
          onSave={() => handleSave("yum")}
        />
      )}

      {allRepos.apk && (
        <ApkSection
          repos={allRepos.apk}
          onUpdate={(r) => handleUpdate("apk", r)}
          saving={saving.apk ?? false}
          saved={saved.apk ?? false}
          onSave={() => handleSave("apk")}
        />
      )}
    </div>
  )
}
