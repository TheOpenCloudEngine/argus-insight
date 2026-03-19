"use client"

import { useCallback, useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import {
  Brain,
  Database,
  FunctionSquare,
  HardDrive,
  MoreHorizontal,
  Table2,
  Trash2,
} from "lucide-react"

import { Button } from "@workspace/ui/components/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@workspace/ui/components/dropdown-menu"
import { UCBreadcrumbs } from "@/features/unity-catalog/components/uc-breadcrumbs"
import { UCDescriptionBox } from "@/features/unity-catalog/components/uc-description-box"
import { UCDetailsLayout } from "@/features/unity-catalog/components/uc-details-layout"
import { UCTimestampMetadata } from "@/features/unity-catalog/components/uc-metadata-list"
import { UCEntityTable } from "@/features/unity-catalog/components/uc-entity-table"
import { UCDeleteDialog } from "@/features/unity-catalog/components/uc-delete-dialog"
import {
  getSchema,
  listTables,
  listVolumes,
  listFunctions,
  listModels,
  updateSchema,
  deleteSchema,
} from "@/features/unity-catalog/api"
import type { Schema, UCTable, Volume, UCFunction, Model } from "@/features/unity-catalog/data/schema"

type TabKey = "tables" | "volumes" | "functions" | "models"

const tabs: { key: TabKey; label: string; icon: React.ReactNode }[] = [
  { key: "tables", label: "Tables", icon: <Table2 className="h-4 w-4" /> },
  { key: "volumes", label: "Volumes", icon: <HardDrive className="h-4 w-4" /> },
  { key: "functions", label: "Functions", icon: <FunctionSquare className="h-4 w-4" /> },
  { key: "models", label: "Models", icon: <Brain className="h-4 w-4" /> },
]

export default function SchemaDetailsPage() {
  const params = useParams<{ catalog: string; schema: string }>()
  const router = useRouter()
  const { catalog: catalogName, schema: schemaName } = params
  const fullName = `${catalogName}.${schemaName}`

  const [schema, setSchema] = useState<Schema | null>(null)
  const [activeTab, setActiveTab] = useState<TabKey>("tables")
  const [tables, setTables] = useState<UCTable[]>([])
  const [volumes, setVolumes] = useState<Volume[]>([])
  const [functions, setFunctions] = useState<UCFunction[]>([])
  const [models, setModels] = useState<Model[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [deleteOpen, setDeleteOpen] = useState(false)

  const loadData = useCallback(async () => {
    setIsLoading(true)
    try {
      const [sch, t, v, f, m] = await Promise.all([
        getSchema(fullName),
        listTables(catalogName, schemaName),
        listVolumes(catalogName, schemaName),
        listFunctions(catalogName, schemaName),
        listModels(catalogName, schemaName),
      ])
      setSchema(sch)
      setTables(t)
      setVolumes(v)
      setFunctions(f)
      setModels(m)
    } finally {
      setIsLoading(false)
    }
  }, [fullName, catalogName, schemaName])

  useEffect(() => { loadData() }, [loadData])

  const UC_BASE = "/dashboard/unity-catalog"

  return (
    <>
      <div className="flex flex-1 flex-col gap-4 p-4">
        <div className="flex items-center justify-between">
          <UCBreadcrumbs items={[
            { label: "Catalogs", href: UC_BASE },
            { label: catalogName, href: `${UC_BASE}/catalogs/${catalogName}` },
            { label: schemaName },
          ]} />
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="h-8 w-8">
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem className="text-destructive" onClick={() => setDeleteOpen(true)}>
                <Trash2 className="mr-2 h-4 w-4" /> Delete Schema
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        <UCDetailsLayout
          sidebar={
            schema && <UCTimestampMetadata createdAt={schema.created_at} updatedAt={schema.updated_at} />
          }
        >
          {schema && (
            <UCDescriptionBox
              comment={schema.comment}
              onEdit={async (comment) => {
                await updateSchema(fullName, { comment })
                loadData()
              }}
            />
          )}

          {/* Tabs */}
          <div className="space-y-4">
            <div className="flex gap-1 rounded-lg border p-1">
              {tabs.map((tab) => (
                <button
                  key={tab.key}
                  type="button"
                  onClick={() => setActiveTab(tab.key)}
                  className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm transition-colors ${
                    activeTab === tab.key
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:text-foreground hover:bg-muted"
                  }`}
                >
                  {tab.icon}
                  {tab.label}
                </button>
              ))}
            </div>

            {activeTab === "tables" && (
              <UCEntityTable
                data={tables}
                isLoading={isLoading}
                emptyMessage="No tables in this schema."
                nameIcon={<Table2 className="h-4 w-4 text-muted-foreground" />}
                getHref={(t) => `${UC_BASE}/tables/${catalogName}/${schemaName}/${t.name}`}
                extraColumns={[
                  {
                    header: "Type",
                    cell: (t) => (
                      <span className="rounded border px-1.5 py-0.5 text-xs">{t.table_type ?? "—"}</span>
                    ),
                  },
                ]}
              />
            )}

            {activeTab === "volumes" && (
              <UCEntityTable
                data={volumes}
                isLoading={isLoading}
                emptyMessage="No volumes in this schema."
                nameIcon={<HardDrive className="h-4 w-4 text-muted-foreground" />}
                getHref={(v) => `${UC_BASE}/volumes/${catalogName}/${schemaName}/${v.name}`}
                extraColumns={[
                  {
                    header: "Type",
                    cell: (v) => (
                      <span className="rounded border px-1.5 py-0.5 text-xs">{v.volume_type ?? "—"}</span>
                    ),
                  },
                ]}
              />
            )}

            {activeTab === "functions" && (
              <UCEntityTable
                data={functions}
                isLoading={isLoading}
                emptyMessage="No functions in this schema."
                nameIcon={<FunctionSquare className="h-4 w-4 text-muted-foreground" />}
                getHref={(f) => `${UC_BASE}/functions/${catalogName}/${schemaName}/${f.name}`}
                extraColumns={[
                  {
                    header: "Language",
                    cell: (f) => (
                      <span className="rounded border px-1.5 py-0.5 text-xs">{f.external_language ?? "—"}</span>
                    ),
                  },
                ]}
              />
            )}

            {activeTab === "models" && (
              <UCEntityTable
                data={models}
                isLoading={isLoading}
                emptyMessage="No models in this schema."
                nameIcon={<Brain className="h-4 w-4 text-muted-foreground" />}
                getHref={(m) => `${UC_BASE}/models/${catalogName}/${schemaName}/${m.name}`}
              />
            )}
          </div>
        </UCDetailsLayout>
      </div>

      <UCDeleteDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        entityType="schema"
        entityName={fullName}
        onConfirm={async () => {
          await deleteSchema(fullName)
          router.push(`${UC_BASE}/catalogs/${catalogName}`)
        }}
      />
    </>
  )
}
