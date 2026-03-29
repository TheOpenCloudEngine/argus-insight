"use client"

import { useCallback, useEffect, useState } from "react"
import { Check, Eye, EyeOff, Loader2, Play, Save, X } from "lucide-react"

import { Button } from "@workspace/ui/components/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@workspace/ui/components/card"
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@workspace/ui/components/select"

import {
  fetchGitlabConfig, fetchGitlabToken,
  testGitlabConnection, updateGitlabConfig,
} from "../api"

export function GitlabSettings() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null)

  const [url, setUrl] = useState("")
  const [token, setToken] = useState("")
  const [groupPath, setGroupPath] = useState("workspaces")
  const [defaultBranch, setDefaultBranch] = useState("main")
  const [visibility, setVisibility] = useState("internal")
  const [showToken, setShowToken] = useState(false)
  const [realToken, setRealToken] = useState<string | null>(null)

  const loadConfig = useCallback(async () => {
    try {
      setLoading(true)
      const cfg = await fetchGitlabConfig()
      setUrl(cfg.url)
      setToken(cfg.token)
      setGroupPath(cfg.group_path)
      setDefaultBranch(cfg.default_branch)
      setVisibility(cfg.project_visibility)
    } catch {
      setMessage({ type: "error", text: "Failed to load GitLab configuration" })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadConfig()
  }, [loadConfig])

  const handleToggleToken = async () => {
    if (!showToken && realToken === null) {
      try {
        const secret = await fetchGitlabToken()
        setRealToken(secret)
        setToken(secret)
      } catch {
        // ignore
      }
    }
    setShowToken(!showToken)
  }

  const handleSave = async () => {
    setSaving(true)
    setMessage(null)
    try {
      await updateGitlabConfig({
        url, token, group_path: groupPath,
        default_branch: defaultBranch,
        project_visibility: visibility,
      })
      setMessage({ type: "success", text: "GitLab configuration saved" })
    } catch (e) {
      setMessage({ type: "error", text: e instanceof Error ? e.message : "Save failed" })
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async () => {
    setTesting(true)
    setMessage(null)
    try {
      // Resolve masked token for test
      let testToken = token
      if (testToken === "••••••••") {
        if (realToken) {
          testToken = realToken
        } else {
          testToken = await fetchGitlabToken()
        }
      }
      const result = await testGitlabConnection(url.trim(), testToken.trim())
      setMessage({
        type: result.success ? "success" : "error",
        text: result.message,
      })
    } catch (e) {
      setMessage({ type: "error", text: e instanceof Error ? e.message : "Test failed" })
    } finally {
      setTesting(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="space-y-4 max-w-2xl">
      {message && (
        <div className={`flex items-center gap-2 rounded-md px-3 py-2 text-sm ${
          message.type === "success"
            ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
            : "bg-red-50 text-red-700 border border-red-200"
        }`}>
          {message.type === "success" ? <Check className="h-4 w-4" /> : <X className="h-4 w-4" />}
          {message.text}
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">GitLab</CardTitle>
          <CardDescription>
            Configure GitLab integration for workspace project management.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5 sm:col-span-2">
              <Label>Server URL <span className="text-red-500">*</span></Label>
              <Input
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://gitlab-global.argus-insight.dev.net"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label>Private Token <span className="text-red-500">*</span></Label>
            <div className="relative">
              <Input
                type={showToken ? "text" : "password"}
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="glpat-xxxxxxxxxxxxxxxxxxxx"
                className="pr-10"
              />
              <button
                type="button"
                className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground"
                onClick={handleToggleToken}
              >
                {showToken ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            <p className="text-xs text-muted-foreground">
              Admin or service account token with API scope.
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label>Group Path</Label>
              <Input
                value={groupPath}
                onChange={(e) => setGroupPath(e.target.value)}
                placeholder="workspaces"
              />
              <p className="text-xs text-muted-foreground">
                Top-level group for workspace projects.
              </p>
            </div>
            <div className="space-y-1.5">
              <Label>Default Branch</Label>
              <Input
                value={defaultBranch}
                onChange={(e) => setDefaultBranch(e.target.value)}
                placeholder="main"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label>Project Visibility</Label>
            <Select value={visibility} onValueChange={setVisibility}>
              <SelectTrigger className="w-[240px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="internal">Internal</SelectItem>
                <SelectItem value="private">Private</SelectItem>
                <SelectItem value="public">Public</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Visibility level for newly created workspace projects.
            </p>
          </div>

          <div className="flex items-center gap-2 pt-2">
            <Button onClick={handleSave} disabled={saving || !url.trim()}>
              {saving ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Save className="h-4 w-4 mr-1" />}
              Save
            </Button>
            <Button variant="outline" onClick={handleTest} disabled={testing || !url.trim()}>
              {testing ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Play className="h-4 w-4 mr-1" />}
              Test Connection
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
