"use client"

import { useCallback, useEffect, useState } from "react"
import { Loader2, Save } from "lucide-react"

import { Button } from "@workspace/ui/components/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@workspace/ui/components/card"
import { Checkbox } from "@workspace/ui/components/checkbox"
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"

import { fetchLdapConfig, updateLdapConfig } from "@/features/settings/api"

// --------------------------------------------------------------------------- //
// Types
// --------------------------------------------------------------------------- //

type LdapState = {
  enable_ldap_auth: string
  ldap_url: string
  ad_domain: string
  ldap_bind_user: string
  ldap_bind_password: string
  user_search_base: string
  user_object_class: string
  user_search_filter: string
  user_name_attribute: string
  group_search_base: string
  group_object_class: string
  group_search_filter: string
  group_name_attribute: string
  group_member_attribute: string
}

const LDAP_DEFAULTS: LdapState = {
  enable_ldap_auth: "false",
  ldap_url: "ldap://<SERVER>:389",
  ad_domain: "",
  ldap_bind_user: "",
  ldap_bind_password: "",
  user_search_base: "",
  user_object_class: "person",
  user_search_filter: "",
  user_name_attribute: "uid",
  group_search_base: "",
  group_object_class: "posixGroup",
  group_search_filter: "",
  group_name_attribute: "cn",
  group_member_attribute: "memberUid",
}

// --------------------------------------------------------------------------- //
// Main Component
// --------------------------------------------------------------------------- //

export function LdapSettings() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const [ldap, setLdap] = useState<LdapState>(LDAP_DEFAULTS)

  // Status messages
  const [statusMessage, setStatusMessage] = useState<{ type: "success" | "error"; text: string } | null>(null)

  const loadConfig = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const items = await fetchLdapConfig()
      setLdap({
        enable_ldap_auth: items.enable_ldap_auth ?? LDAP_DEFAULTS.enable_ldap_auth,
        ldap_url: items.ldap_url ?? LDAP_DEFAULTS.ldap_url,
        ad_domain: items.ad_domain ?? LDAP_DEFAULTS.ad_domain,
        ldap_bind_user: items.ldap_bind_user ?? LDAP_DEFAULTS.ldap_bind_user,
        ldap_bind_password: items.ldap_bind_password ?? LDAP_DEFAULTS.ldap_bind_password,
        user_search_base: items.user_search_base ?? LDAP_DEFAULTS.user_search_base,
        user_object_class: items.user_object_class ?? LDAP_DEFAULTS.user_object_class,
        user_search_filter: items.user_search_filter ?? LDAP_DEFAULTS.user_search_filter,
        user_name_attribute: items.user_name_attribute ?? LDAP_DEFAULTS.user_name_attribute,
        group_search_base: items.group_search_base ?? LDAP_DEFAULTS.group_search_base,
        group_object_class: items.group_object_class ?? LDAP_DEFAULTS.group_object_class,
        group_search_filter: items.group_search_filter ?? LDAP_DEFAULTS.group_search_filter,
        group_name_attribute: items.group_name_attribute ?? LDAP_DEFAULTS.group_name_attribute,
        group_member_attribute: items.group_member_attribute ?? LDAP_DEFAULTS.group_member_attribute,
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

  function set(key: keyof LdapState, value: string) {
    setLdap((prev) => ({ ...prev, [key]: value }))
  }

  async function handleSave() {
    setSaving(true)
    try {
      await updateLdapConfig(ldap)
      showStatus("success", "LDAP settings saved successfully")
      await loadConfig()
    } catch (err) {
      showStatus("error", err instanceof Error ? err.message : "Failed to save")
    } finally {
      setSaving(false)
    }
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

      {/* Save button */}
      <div className="flex justify-end">
        <Button size="sm" onClick={handleSave} disabled={saving}>
          {saving ? (
            <Loader2 className="h-4 w-4 animate-spin mr-1.5" />
          ) : (
            <Save className="h-4 w-4 mr-1.5" />
          )}
          Save
        </Button>
      </div>

      {/* Active Directory & LDAP Server */}
      <Card>
        <CardHeader>
          <CardTitle>Active Directory & LDAP Server</CardTitle>
          <CardDescription>
            LDAP server connection and authentication settings
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <Checkbox
                id="enable-ldap-auth"
                checked={ldap.enable_ldap_auth === "true"}
                onCheckedChange={(checked) =>
                  set("enable_ldap_auth", checked === true ? "true" : "false")
                }
              />
              <Label htmlFor="enable-ldap-auth">Enable LDAP Authentication</Label>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="ldap-url">LDAP/AD URL</Label>
                <Input
                  id="ldap-url"
                  value={ldap.ldap_url}
                  onChange={(e) => set("ldap_url", e.target.value)}
                  placeholder="ldap://<SERVER>:389"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="ad-domain">Active Directory Domain</Label>
                <Input
                  id="ad-domain"
                  value={ldap.ad_domain}
                  onChange={(e) => set("ad_domain", e.target.value)}
                  placeholder="e.g. dev.net"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="ldap-bind-user">LDAP Bind User</Label>
                <Input
                  id="ldap-bind-user"
                  value={ldap.ldap_bind_user}
                  onChange={(e) => set("ldap_bind_user", e.target.value)}
                  placeholder="e.g. cn=admin,dc=dev,dc=net"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="ldap-bind-password">LDAP Bind Password</Label>
                <Input
                  id="ldap-bind-password"
                  type="password"
                  value={ldap.ldap_bind_password}
                  onChange={(e) => set("ldap_bind_password", e.target.value)}
                  placeholder="Bind password"
                />
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* LDAP User */}
      <Card>
        <CardHeader>
          <CardTitle>LDAP User</CardTitle>
          <CardDescription>
            User search configuration for LDAP directory
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="user-search-base">User Search Base</Label>
              <Input
                id="user-search-base"
                value={ldap.user_search_base}
                onChange={(e) => set("user_search_base", e.target.value)}
                placeholder="e.g. ou=People,dc=dev,dc=net"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="user-object-class">User Object Class</Label>
              <Input
                id="user-object-class"
                value={ldap.user_object_class}
                onChange={(e) => set("user_object_class", e.target.value)}
                placeholder="e.g. person"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="user-search-filter">User Search Filter</Label>
              <Input
                id="user-search-filter"
                value={ldap.user_search_filter}
                onChange={(e) => set("user_search_filter", e.target.value)}
                placeholder="e.g. (uid={0})"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="user-name-attribute">User Name Attribute</Label>
              <Input
                id="user-name-attribute"
                value={ldap.user_name_attribute}
                onChange={(e) => set("user_name_attribute", e.target.value)}
                placeholder="e.g. uid"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* LDAP Group */}
      <Card>
        <CardHeader>
          <CardTitle>LDAP Group</CardTitle>
          <CardDescription>
            Group search configuration for LDAP directory
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="group-search-base">Group Search Base</Label>
              <Input
                id="group-search-base"
                value={ldap.group_search_base}
                onChange={(e) => set("group_search_base", e.target.value)}
                placeholder="e.g. ou=Group,dc=dev,dc=net"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="group-object-class">Group Object Class</Label>
              <Input
                id="group-object-class"
                value={ldap.group_object_class}
                onChange={(e) => set("group_object_class", e.target.value)}
                placeholder="e.g. posixGroup"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="group-search-filter">Group Search Filter</Label>
              <Input
                id="group-search-filter"
                value={ldap.group_search_filter}
                onChange={(e) => set("group_search_filter", e.target.value)}
                placeholder="e.g. (cn={0})"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="group-name-attribute">Group Name Attribute</Label>
              <Input
                id="group-name-attribute"
                value={ldap.group_name_attribute}
                onChange={(e) => set("group_name_attribute", e.target.value)}
                placeholder="e.g. cn"
              />
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="group-member-attribute">Group Member Attribute</Label>
              <Input
                id="group-member-attribute"
                value={ldap.group_member_attribute}
                onChange={(e) => set("group_member_attribute", e.target.value)}
                placeholder="e.g. memberUid"
              />
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
