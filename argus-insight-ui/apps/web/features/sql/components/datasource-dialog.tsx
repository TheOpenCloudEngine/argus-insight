"use client"

import React, { useCallback, useState } from "react"
import { CheckCircle2, Loader2, XCircle } from "lucide-react"
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
import type { DatasourceCreate, DatasourceTestResult, EngineType } from "../types"
import { useSql } from "./sql-provider"

const ENGINE_DEFAULTS: Record<EngineType, { port: number; database: string }> = {
  trino: { port: 8080, database: "" },
  starrocks: { port: 9030, database: "" },
  postgresql: { port: 5432, database: "postgres" },
  mariadb: { port: 3306, database: "" },
}

export function DatasourceDialog() {
  const { dialog, setDialog, refreshDatasources } = useSql()

  const [form, setForm] = useState<DatasourceCreate>({
    name: "",
    engine_type: "trino",
    host: "",
    port: 8080,
    database_name: "",
    username: "",
    password: "",
    description: "",
  })
  const [testResult, setTestResult] = useState<DatasourceTestResult | null>(null)
  const [testing, setTesting] = useState(false)
  const [saving, setSaving] = useState(false)

  const isOpen = dialog === "add-datasource"

  const handleClose = useCallback(() => {
    setDialog(null)
    setForm({
      name: "",
      engine_type: "trino",
      host: "",
      port: 8080,
      database_name: "",
      username: "",
      password: "",
      description: "",
    })
    setTestResult(null)
  }, [setDialog])

  const handleEngineChange = useCallback((engine: EngineType) => {
    const defaults = ENGINE_DEFAULTS[engine]
    setForm((prev) => ({
      ...prev,
      engine_type: engine,
      port: defaults.port,
      database_name: defaults.database,
    }))
    setTestResult(null)
  }, [])

  const handleTest = useCallback(async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const result = await api.testDatasourceConnection(form)
      setTestResult(result)
    } catch (e) {
      setTestResult({
        success: false,
        message: e instanceof Error ? e.message : "Test failed",
        latency_ms: null,
      })
    } finally {
      setTesting(false)
    }
  }, [form])

  const handleSave = useCallback(async () => {
    setSaving(true)
    try {
      await api.createDatasource(form)
      await refreshDatasources()
      handleClose()
    } catch (e) {
      console.error("Failed to create datasource", e)
    } finally {
      setSaving(false)
    }
  }, [form, refreshDatasources, handleClose])

  const canSave = form.name.trim() && form.host.trim() && form.port > 0

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && handleClose()}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Add Datasource</DialogTitle>
          <DialogDescription>
            Register a new database connection for SQL queries.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-2">
          {/* Name */}
          <div className="grid gap-1.5">
            <Label htmlFor="ds-name">Name</Label>
            <Input
              id="ds-name"
              placeholder="My Database"
              value={form.name}
              onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
            />
          </div>

          {/* Engine type */}
          <div className="grid gap-1.5">
            <Label>Engine</Label>
            <div className="flex gap-2">
              {(["trino", "starrocks", "postgresql", "mariadb"] as EngineType[]).map((engine) => {
                const labels: Record<string, string> = { trino: "Trino", starrocks: "StarRocks", postgresql: "PostgreSQL", mariadb: "MariaDB" }
                return (
                  <Button
                    key={engine}
                    variant={form.engine_type === engine ? "default" : "outline"}
                    size="sm"
                    className="flex-1 text-xs"
                    onClick={() => handleEngineChange(engine)}
                  >
                    {labels[engine]}
                  </Button>
                )
              })}
            </div>
          </div>

          {/* Host + Port */}
          <div className="grid grid-cols-3 gap-2">
            <div className="col-span-2 grid gap-1.5">
              <Label htmlFor="ds-host">Host</Label>
              <Input
                id="ds-host"
                placeholder="localhost"
                value={form.host}
                onChange={(e) => setForm((p) => ({ ...p, host: e.target.value }))}
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="ds-port">Port</Label>
              <Input
                id="ds-port"
                type="number"
                value={form.port}
                onChange={(e) => setForm((p) => ({ ...p, port: Number(e.target.value) }))}
              />
            </div>
          </div>

          {/* Database */}
          <div className="grid gap-1.5">
            <Label htmlFor="ds-db">
              {form.engine_type === "trino" ? "Catalog" : "Database"}
            </Label>
            <Input
              id="ds-db"
              placeholder={form.engine_type === "trino" ? "hive" : "mydb"}
              value={form.database_name}
              onChange={(e) => setForm((p) => ({ ...p, database_name: e.target.value }))}
            />
          </div>

          {/* Username + Password */}
          <div className="grid grid-cols-2 gap-2">
            <div className="grid gap-1.5">
              <Label htmlFor="ds-user">Username</Label>
              <Input
                id="ds-user"
                placeholder="user"
                value={form.username}
                onChange={(e) => setForm((p) => ({ ...p, username: e.target.value }))}
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="ds-pass">Password</Label>
              <Input
                id="ds-pass"
                type="password"
                placeholder="password"
                value={form.password}
                onChange={(e) => setForm((p) => ({ ...p, password: e.target.value }))}
              />
            </div>
          </div>

          {/* Test result */}
          {testResult && (
            <div
              className={`flex items-center gap-2 rounded-md p-2 text-xs ${
                testResult.success
                  ? "bg-green-500/10 text-green-700 dark:text-green-400"
                  : "bg-destructive/10 text-destructive"
              }`}
            >
              {testResult.success ? (
                <CheckCircle2 className="h-4 w-4 shrink-0" />
              ) : (
                <XCircle className="h-4 w-4 shrink-0" />
              )}
              <span>{testResult.message}</span>
              {testResult.latency_ms != null && (
                <span className="ml-auto text-[10px]">{testResult.latency_ms.toFixed(0)}ms</span>
              )}
            </div>
          )}
        </div>

        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={handleTest} disabled={testing || !form.host.trim()}>
            {testing ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : null}
            Test Connection
          </Button>
          <Button onClick={handleSave} disabled={saving || !canSave}>
            {saving ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : null}
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
