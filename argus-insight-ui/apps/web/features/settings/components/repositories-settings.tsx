"use client"

import { useCallback, useEffect, useState } from "react"
import { CheckCircle2, Copy, Disc, ExternalLink, Loader2, Plus, Trash2 } from "lucide-react"
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

interface AptRepo { type: string; url: string; dist: string; components: string; enabled: boolean; trusted: boolean }
interface YumRepo { repo_id: string; name: string; baseurl: string; gpgcheck: boolean; enabled: boolean }
interface ApkRepo { url: string; enabled: boolean }

interface OsRepos {
  label: string
  pkg_type: "apt" | "yum" | "apk"
  builtin: Record<string, unknown>[]
  custom: Record<string, unknown>[]
}

type AllRepos = Record<string, OsRepos>

/* ------------------------------------------------------------------ */
/*  ISO Download Links                                                 */
/* ------------------------------------------------------------------ */

const ISO_LINKS: Record<string, { name: string; url: string }[]> = {
  "debian-11": [
    { name: "ISO Image", url: "https://cdimage.debian.org/cdimage/archive/11.11.0/amd64/iso-cd/" },
    { name: "Package Mirror", url: "http://deb.debian.org/debian" },
    { name: "Security Updates", url: "http://security.debian.org/debian-security" },
  ],
  "debian-12": [
    { name: "ISO Image", url: "https://cdimage.debian.org/debian-cd/current/amd64/iso-cd/" },
    { name: "Package Mirror", url: "http://deb.debian.org/debian" },
    { name: "Security Updates", url: "http://security.debian.org/debian-security" },
  ],
  "debian-13": [
    { name: "ISO Image", url: "https://cdimage.debian.org/cdimage/trixie_di_alpha1/amd64/iso-cd/" },
    { name: "Package Mirror", url: "http://deb.debian.org/debian" },
    { name: "Security Updates", url: "http://security.debian.org/debian-security" },
  ],
  "ubuntu-22.04": [
    { name: "ISO Image", url: "https://releases.ubuntu.com/22.04/" },
    { name: "Package Mirror", url: "http://archive.ubuntu.com/ubuntu" },
    { name: "Security Updates", url: "http://security.ubuntu.com/ubuntu" },
  ],
  "ubuntu-24.04": [
    { name: "ISO Image", url: "https://releases.ubuntu.com/24.04/" },
    { name: "Package Mirror", url: "http://archive.ubuntu.com/ubuntu" },
    { name: "Security Updates", url: "http://security.ubuntu.com/ubuntu" },
  ],
  "rocky-9": [
    { name: "ISO Image", url: "https://rockylinux.org/download" },
    { name: "BaseOS Mirror", url: "http://dl.rockylinux.org/pub/rocky/9/BaseOS/x86_64/os/" },
    { name: "AppStream Mirror", url: "http://dl.rockylinux.org/pub/rocky/9/AppStream/x86_64/os/" },
  ],
  "alpine-3.20": [
    { name: "ISO Image", url: "https://dl-cdn.alpinelinux.org/alpine/v3.20/releases/x86_64/" },
    { name: "Package Mirror (main)", url: "https://dl-cdn.alpinelinux.org/alpine/v3.20/main" },
    { name: "Package Mirror (community)", url: "https://dl-cdn.alpinelinux.org/alpine/v3.20/community" },
  ],
  "alpine-3.21": [
    { name: "ISO Image", url: "https://dl-cdn.alpinelinux.org/alpine/v3.21/releases/x86_64/" },
    { name: "Package Mirror (main)", url: "https://dl-cdn.alpinelinux.org/alpine/v3.21/main" },
    { name: "Package Mirror (community)", url: "https://dl-cdn.alpinelinux.org/alpine/v3.21/community" },
  ],
}

function CopyBtn({ value }: { value: string }) {
  const [copied, setCopied] = useState(false)
  const handleCopy = async () => {
    try { await navigator.clipboard.writeText(value) } catch {
      const ta = document.createElement("textarea"); ta.value = value; ta.style.position = "fixed"; ta.style.opacity = "0"
      document.body.appendChild(ta); ta.select(); document.execCommand("copy"); document.body.removeChild(ta)
    }
    setCopied(true); setTimeout(() => setCopied(false), 1500)
  }
  return (
    <button onClick={handleCopy} className="text-muted-foreground hover:text-foreground shrink-0">
      {copied ? <CheckCircle2 className="h-3.5 w-3.5 text-green-600" /> : <Copy className="h-3.5 w-3.5" />}
    </button>
  )
}

function IsoDialog({ open, onOpenChange, osKey, label }: { open: boolean; onOpenChange: (o: boolean) => void; osKey: string; label: string }) {
  const links = ISO_LINKS[osKey] || []
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{label} - Downloads</DialogTitle>
          <DialogDescription>Official ISO and package repository download links.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3 py-2">
          {links.length === 0 ? (
            <p className="text-sm text-muted-foreground">No download links available for this OS.</p>
          ) : (
            links.map((link) => (
              <div key={link.name} className="space-y-1">
                <p className="text-xs font-medium text-muted-foreground">{link.name}</p>
                <div className="flex items-center gap-2 rounded-md border px-3 py-2">
                  <a href={link.url} target="_blank" rel="noopener noreferrer" className="flex-1 truncate text-sm text-blue-600 hover:underline dark:text-blue-400 font-mono">
                    {link.url}
                  </a>
                  <a href={link.url} target="_blank" rel="noopener noreferrer" className="text-muted-foreground hover:text-foreground shrink-0">
                    <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                  <CopyBtn value={link.url} />
                </div>
              </div>
            ))
          )}
        </div>
        <div className="flex justify-end">
          <Button size="sm" onClick={() => onOpenChange(false)}>Close</Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}

/* ------------------------------------------------------------------ */
/*  APT Add Dialog                                                     */
/* ------------------------------------------------------------------ */

function AptAddDialog({ open, onOpenChange, onAdd, defaultDist }: { open: boolean; onOpenChange: (o: boolean) => void; onAdd: (r: AptRepo) => void; defaultDist: string }) {
  const [form, setForm] = useState<AptRepo>({ type: "deb", url: "", dist: defaultDist, components: "main", enabled: true, trusted: true })
  // Reset dist when dialog opens with new defaultDist
  useEffect(() => { if (open) setForm((f) => ({ ...f, dist: defaultDist })) }, [open, defaultDist])
  const handleAdd = () => { if (form.url && form.dist) { onAdd({ ...form }); onOpenChange(false); setForm({ type: "deb", url: "", dist: defaultDist, components: "main", enabled: true, trusted: true }) } }
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader><DialogTitle>Add APT Repository</DialogTitle><DialogDescription>Add a custom Debian/Ubuntu package repository.</DialogDescription></DialogHeader>
        <div className="space-y-3">
          <div className="grid grid-cols-4 gap-2">
            <div><Label className="text-xs">Type</Label><Select value={form.type} onValueChange={(v) => setForm({ ...form, type: v })}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="deb">deb</SelectItem><SelectItem value="deb-src">deb-src</SelectItem></SelectContent></Select></div>
            <div className="col-span-3"><Label className="text-xs">URL</Label><Input value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} placeholder="http://10.0.1.50:8081/repository/apt-public/" /></div>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div><Label className="text-xs">Distribution</Label><Input value={form.dist} onChange={(e) => setForm({ ...form, dist: e.target.value })} placeholder="bookworm" /></div>
            <div><Label className="text-xs">Components</Label><Input value={form.components} onChange={(e) => setForm({ ...form, components: e.target.value })} placeholder="main" /></div>
          </div>
          <label className="flex items-center gap-2 text-sm"><Checkbox checked={form.trusted} onCheckedChange={(v) => setForm({ ...form, trusted: !!v })} />Trusted (skip GPG verification)</label>
        </div>
        <div className="flex justify-end gap-2 pt-2"><Button variant="outline" size="sm" onClick={() => onOpenChange(false)}>Cancel</Button><Button size="sm" onClick={handleAdd} disabled={!form.url || !form.dist}>Add</Button></div>
      </DialogContent>
    </Dialog>
  )
}

/* ------------------------------------------------------------------ */
/*  YUM Add Dialog                                                     */
/* ------------------------------------------------------------------ */

function YumAddDialog({ open, onOpenChange, onAdd }: { open: boolean; onOpenChange: (o: boolean) => void; onAdd: (r: YumRepo) => void }) {
  const [form, setForm] = useState<YumRepo>({ repo_id: "", name: "", baseurl: "", gpgcheck: false, enabled: true })
  const handleAdd = () => { if (form.repo_id && form.baseurl) { onAdd({ ...form }); onOpenChange(false); setForm({ repo_id: "", name: "", baseurl: "", gpgcheck: false, enabled: true }) } }
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader><DialogTitle>Add YUM Repository</DialogTitle><DialogDescription>Add a custom RHEL/CentOS package repository.</DialogDescription></DialogHeader>
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-2">
            <div><Label className="text-xs">Repo ID</Label><Input value={form.repo_id} onChange={(e) => setForm({ ...form, repo_id: e.target.value })} placeholder="argus-custom" /></div>
            <div><Label className="text-xs">Name</Label><Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Argus Custom Repo" /></div>
          </div>
          <div><Label className="text-xs">Base URL</Label><Input value={form.baseurl} onChange={(e) => setForm({ ...form, baseurl: e.target.value })} placeholder="http://10.0.1.50:8081/repository/yum-public/" /></div>
          <label className="flex items-center gap-2 text-sm"><Checkbox checked={form.gpgcheck} onCheckedChange={(v) => setForm({ ...form, gpgcheck: !!v })} />GPG Check</label>
        </div>
        <div className="flex justify-end gap-2 pt-2"><Button variant="outline" size="sm" onClick={() => onOpenChange(false)}>Cancel</Button><Button size="sm" onClick={handleAdd} disabled={!form.repo_id || !form.baseurl}>Add</Button></div>
      </DialogContent>
    </Dialog>
  )
}

/* ------------------------------------------------------------------ */
/*  APK Add Dialog                                                     */
/* ------------------------------------------------------------------ */

function ApkAddDialog({ open, onOpenChange, onAdd }: { open: boolean; onOpenChange: (o: boolean) => void; onAdd: (r: ApkRepo) => void }) {
  const [url, setUrl] = useState("")
  const handleAdd = () => { if (url) { onAdd({ url, enabled: true }); onOpenChange(false); setUrl("") } }
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader><DialogTitle>Add APK Repository</DialogTitle><DialogDescription>Add a custom Alpine package repository URL.</DialogDescription></DialogHeader>
        <div><Label className="text-xs">Repository URL</Label><Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="http://10.0.1.50:8081/repository/apk-public/v3.21/main" /></div>
        <div className="flex justify-end gap-2 pt-2"><Button variant="outline" size="sm" onClick={() => onOpenChange(false)}>Cancel</Button><Button size="sm" onClick={handleAdd} disabled={!url}>Add</Button></div>
      </DialogContent>
    </Dialog>
  )
}

/* ------------------------------------------------------------------ */
/*  Generic OS+Version Section                                         */
/* ------------------------------------------------------------------ */

function RepoSection({
  osKey,
  repos,
  onUpdate,
  saving,
  saved,
  onSave,
}: {
  osKey: string
  repos: OsRepos
  onUpdate: (repos: OsRepos) => void
  saving: boolean
  saved: boolean
  onSave: () => void
}) {
  const [addOpen, setAddOpen] = useState(false)
  const [isoOpen, setIsoOpen] = useState(false)

  const toggleBuiltin = (idx: number) => {
    const updated = [...repos.builtin]; updated[idx] = { ...updated[idx], enabled: !updated[idx].enabled }; onUpdate({ ...repos, builtin: updated })
  }
  const updateBuiltin = (idx: number, field: string, value: string) => {
    const updated = [...repos.builtin]; updated[idx] = { ...updated[idx], [field]: value }; onUpdate({ ...repos, builtin: updated })
  }
  const toggleCustom = (idx: number) => {
    const updated = [...repos.custom]; updated[idx] = { ...updated[idx], enabled: !updated[idx].enabled }; onUpdate({ ...repos, custom: updated })
  }
  const removeCustom = (idx: number) => { onUpdate({ ...repos, custom: repos.custom.filter((_, i) => i !== idx) }) }
  const addCustom = (r: Record<string, unknown>) => { onUpdate({ ...repos, custom: [...repos.custom, r] }) }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-3">
        <div className="flex items-center gap-2">
          <CardTitle className="text-sm">{repos.label}</CardTitle>
          <Badge variant="outline" className="text-[10px]">{repos.pkg_type.toUpperCase()}</Badge>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" className="text-xs" onClick={() => setAddOpen(true)}>
            <Plus className="mr-1.5 h-3.5 w-3.5" />Add Repo
          </Button>
          {ISO_LINKS[osKey] && (
            <Button variant="outline" size="sm" className="text-xs" onClick={() => setIsoOpen(true)}>
              <Disc className="mr-1.5 h-3.5 w-3.5" />ISO
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Built-in */}
        <div>
          <p className="text-xs font-medium text-muted-foreground mb-2">Built-in</p>
          <div className="space-y-1.5">
            {repos.pkg_type === "apt" && (repos.builtin as AptRepo[]).map((r, i) => (
              <div key={i} className="flex items-center gap-2 text-sm px-2 py-1">
                <Checkbox checked={r.enabled} onCheckedChange={() => toggleBuiltin(i)} />
                <Badge variant="outline" className="text-[10px] font-mono shrink-0">{r.type}</Badge>
                <Input className="h-7 text-xs font-mono flex-1" value={r.url} onChange={(e) => updateBuiltin(i, "url", e.target.value)} />
                <Input className="h-7 text-xs font-mono w-32" value={r.dist} onChange={(e) => updateBuiltin(i, "dist", e.target.value)} />
                <Input className="h-7 text-xs font-mono w-36" value={r.components} onChange={(e) => updateBuiltin(i, "components", e.target.value)} />
              </div>
            ))}
            {repos.pkg_type === "yum" && (repos.builtin as YumRepo[]).map((r, i) => (
              <div key={i} className="flex items-center gap-2 text-sm px-2 py-1">
                <Checkbox checked={r.enabled} onCheckedChange={() => toggleBuiltin(i)} />
                <Badge variant="outline" className="text-[10px] font-mono shrink-0">[{r.repo_id}]</Badge>
                <Input className="h-7 text-xs w-40" value={r.name} onChange={(e) => updateBuiltin(i, "name", e.target.value)} />
                <Input className="h-7 text-xs font-mono flex-1" value={r.baseurl} onChange={(e) => updateBuiltin(i, "baseurl", e.target.value)} />
              </div>
            ))}
            {repos.pkg_type === "apk" && (repos.builtin as ApkRepo[]).map((r, i) => (
              <div key={i} className="flex items-center gap-2 text-sm px-2 py-1">
                <Checkbox checked={r.enabled} onCheckedChange={() => toggleBuiltin(i)} />
                <Input className="h-7 text-xs font-mono flex-1" value={r.url} onChange={(e) => updateBuiltin(i, "url", e.target.value)} />
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
              {repos.pkg_type === "apt" && (repos.custom as AptRepo[]).map((r, i) => (
                <div key={i} className="flex items-center gap-2 text-sm px-2 py-1 hover:bg-muted/50 rounded">
                  <Checkbox checked={r.enabled} onCheckedChange={() => toggleCustom(i)} />
                  <Badge variant="outline" className="text-[10px] font-mono">{r.type}</Badge>
                  <span className="truncate font-mono text-xs flex-1">{r.url} {r.dist} {r.components}</span>
                  {r.trusted && <Badge variant="secondary" className="text-[10px]">trusted</Badge>}
                  <Button variant="ghost" size="icon" className="h-6 w-6 text-red-500" onClick={() => removeCustom(i)}><Trash2 className="h-3 w-3" /></Button>
                </div>
              ))}
              {repos.pkg_type === "yum" && (repos.custom as YumRepo[]).map((r, i) => (
                <div key={i} className="flex items-center gap-2 text-sm px-2 py-1 hover:bg-muted/50 rounded">
                  <Checkbox checked={r.enabled} onCheckedChange={() => toggleCustom(i)} />
                  <Badge variant="outline" className="text-[10px] font-mono">[{r.repo_id}]</Badge>
                  <span className="truncate text-xs flex-1">{r.name}</span>
                  <span className="truncate font-mono text-[10px] text-muted-foreground max-w-[200px]">{r.baseurl}</span>
                  {!r.gpgcheck && <Badge variant="secondary" className="text-[10px]">no-gpg</Badge>}
                  <Button variant="ghost" size="icon" className="h-6 w-6 text-red-500" onClick={() => removeCustom(i)}><Trash2 className="h-3 w-3" /></Button>
                </div>
              ))}
              {repos.pkg_type === "apk" && (repos.custom as ApkRepo[]).map((r, i) => (
                <div key={i} className="flex items-center gap-2 text-sm px-2 py-1 hover:bg-muted/50 rounded">
                  <Checkbox checked={r.enabled} onCheckedChange={() => toggleCustom(i)} />
                  <span className="truncate font-mono text-xs flex-1">{r.url}</span>
                  <Button variant="ghost" size="icon" className="h-6 w-6 text-red-500" onClick={() => removeCustom(i)}><Trash2 className="h-3 w-3" /></Button>
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

      {/* Add dialogs */}
      {repos.pkg_type === "apt" && <AptAddDialog open={addOpen} onOpenChange={setAddOpen} onAdd={(r) => addCustom(r)} defaultDist={(repos.builtin[0] as AptRepo)?.dist?.replace(/-.*/, "") || ""} />}
      {repos.pkg_type === "yum" && <YumAddDialog open={addOpen} onOpenChange={setAddOpen} onAdd={(r) => addCustom(r)} />}
      {repos.pkg_type === "apk" && <ApkAddDialog open={addOpen} onOpenChange={setAddOpen} onAdd={(r) => addCustom(r)} />}
      <IsoDialog open={isoOpen} onOpenChange={setIsoOpen} osKey={osKey} label={repos.label} />
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

  const handleUpdate = (osKey: string, repos: OsRepos) => {
    setAllRepos((prev) => ({ ...prev, [osKey]: repos }))
    setSaved((prev) => ({ ...prev, [osKey]: false }))
  }

  const handleSave = async (osKey: string) => {
    const repos = allRepos[osKey]
    if (!repos) return
    setSaving((prev) => ({ ...prev, [osKey]: true }))
    try {
      const res = await authFetch(`/api/v1/settings/repositories/${osKey}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ builtin: repos.builtin, custom: repos.custom }),
      })
      if (res.ok) {
        setSaved((prev) => ({ ...prev, [osKey]: true }))
        setTimeout(() => setSaved((prev) => ({ ...prev, [osKey]: false })), 2000)
      }
    } catch { /* ignore */ }
    setSaving((prev) => ({ ...prev, [osKey]: false }))
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  // Group by pkg_type for visual separation
  const aptKeys = Object.keys(allRepos).filter((k) => allRepos[k].pkg_type === "apt")
  const yumKeys = Object.keys(allRepos).filter((k) => allRepos[k].pkg_type === "yum")
  const apkKeys = Object.keys(allRepos).filter((k) => allRepos[k].pkg_type === "apk")

  return (
    <div className="space-y-6">
      <p className="text-sm text-muted-foreground">
        Configure OS-level package repositories per OS version. These are injected into service containers during deployment.
      </p>

      {aptKeys.length > 0 && (
        <div className="space-y-4">
          {aptKeys.map((k) => (
            <RepoSection key={k} osKey={k} repos={allRepos[k]} onUpdate={(r) => handleUpdate(k, r)} saving={saving[k] ?? false} saved={saved[k] ?? false} onSave={() => handleSave(k)} />
          ))}
        </div>
      )}

      {yumKeys.length > 0 && (
        <div className="space-y-4">
          {yumKeys.map((k) => (
            <RepoSection key={k} osKey={k} repos={allRepos[k]} onUpdate={(r) => handleUpdate(k, r)} saving={saving[k] ?? false} saved={saved[k] ?? false} onSave={() => handleSave(k)} />
          ))}
        </div>
      )}

      {apkKeys.length > 0 && (
        <div className="space-y-4">
          {apkKeys.map((k) => (
            <RepoSection key={k} osKey={k} repos={allRepos[k]} onUpdate={(r) => handleUpdate(k, r)} saving={saving[k] ?? false} saved={saved[k] ?? false} onSave={() => handleSave(k)} />
          ))}
        </div>
      )}
    </div>
  )
}
