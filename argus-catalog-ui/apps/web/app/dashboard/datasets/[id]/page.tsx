"use client"

import { useCallback, useEffect, useState } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import {
  ArrowLeft,
  BookOpen,
  Columns3,
  Database,
  Tags,
  Users,
} from "lucide-react"

import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import { Card, CardContent, CardHeader, CardTitle } from "@workspace/ui/components/card"
import { Separator } from "@workspace/ui/components/separator"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@workspace/ui/components/tabs"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@workspace/ui/components/table"
import { DashboardHeader } from "@/components/dashboard-header"
import { fetchDataset } from "@/features/datasets/api"
import type { DatasetDetail } from "@/features/datasets/data/schema"

export default function DatasetDetailPage() {
  const params = useParams()
  const datasetId = Number(params.id)
  const [dataset, setDataset] = useState<DatasetDetail | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setIsLoading(true)
      const data = await fetchDataset(datasetId)
      setDataset(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load dataset")
    } finally {
      setIsLoading(false)
    }
  }, [datasetId])

  useEffect(() => {
    load()
  }, [load])

  if (isLoading) {
    return (
      <>
        <DashboardHeader title="Dataset" />
        <div className="flex items-center justify-center p-8">
          <p className="text-muted-foreground">Loading dataset...</p>
        </div>
      </>
    )
  }

  if (error || !dataset) {
    return (
      <>
        <DashboardHeader title="Dataset" />
        <div className="flex flex-col items-center justify-center gap-4 p-8">
          <p className="text-destructive">{error || "Dataset not found"}</p>
          <Button variant="outline" asChild>
            <Link href="/dashboard/datasets">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Datasets
            </Link>
          </Button>
        </div>
      </>
    )
  }

  return (
    <>
      <DashboardHeader title={dataset.name} />
      <div className="flex flex-1 flex-col gap-4 p-4">
        {/* Back button */}
        <div>
          <Button variant="ghost" size="sm" asChild>
            <Link href="/dashboard/datasets">
              <ArrowLeft className="mr-1 h-4 w-4" />
              Back
            </Link>
          </Button>
        </div>

        {/* Dataset header info */}
        <Card>
          <CardHeader>
            <div className="flex items-start justify-between">
              <div className="space-y-1">
                <CardTitle className="text-xl">{dataset.name}</CardTitle>
                <p className="text-sm text-muted-foreground font-mono">
                  {dataset.urn}
                </p>
              </div>
              <div className="flex gap-2">
                <Badge
                  variant={
                    dataset.status === "active"
                      ? "default"
                      : dataset.status === "deprecated"
                        ? "secondary"
                        : "destructive"
                  }
                >
                  {dataset.status}
                </Badge>
                <Badge variant="outline">{dataset.origin}</Badge>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 text-sm">
              <div>
                <span className="text-muted-foreground">Platform</span>
                <div className="flex items-center gap-1.5 mt-1 font-medium">
                  <Database className="h-4 w-4" />
                  {dataset.platform.display_name}
                </div>
              </div>
              <div>
                <span className="text-muted-foreground">Qualified Name</span>
                <p className="mt-1 font-medium">{dataset.qualified_name || "-"}</p>
              </div>
              <div>
                <span className="text-muted-foreground">Created</span>
                <p className="mt-1 font-medium">
                  {new Date(dataset.created_at).toLocaleDateString()}
                </p>
              </div>
              <div>
                <span className="text-muted-foreground">Updated</span>
                <p className="mt-1 font-medium">
                  {new Date(dataset.updated_at).toLocaleDateString()}
                </p>
              </div>
            </div>
            {dataset.description && (
              <>
                <Separator className="my-4" />
                <div>
                  <span className="text-sm text-muted-foreground">
                    Description
                  </span>
                  <p className="mt-1 text-sm">{dataset.description}</p>
                </div>
              </>
            )}
          </CardContent>
        </Card>

        {/* Tabbed content - DataHub style */}
        <Tabs defaultValue="schema" className="flex-1">
          <TabsList>
            <TabsTrigger value="schema" className="gap-1.5">
              <Columns3 className="h-4 w-4" />
              Schema ({dataset.schema_fields.length})
            </TabsTrigger>
            <TabsTrigger value="tags" className="gap-1.5">
              <Tags className="h-4 w-4" />
              Tags ({dataset.tags.length})
            </TabsTrigger>
            <TabsTrigger value="owners" className="gap-1.5">
              <Users className="h-4 w-4" />
              Owners ({dataset.owners.length})
            </TabsTrigger>
            <TabsTrigger value="glossary" className="gap-1.5">
              <BookOpen className="h-4 w-4" />
              Glossary ({dataset.glossary_terms.length})
            </TabsTrigger>
          </TabsList>

          {/* Schema tab */}
          <TabsContent value="schema" className="mt-4">
            <Card>
              <CardContent className="p-0">
                {dataset.schema_fields.length > 0 ? (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-[50px]">#</TableHead>
                        <TableHead>Field Path</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead>Native Type</TableHead>
                        <TableHead>Nullable</TableHead>
                        <TableHead>Description</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {dataset.schema_fields.map((field, idx) => (
                        <TableRow key={field.id}>
                          <TableCell className="text-muted-foreground">
                            {idx + 1}
                          </TableCell>
                          <TableCell className="font-mono text-sm">
                            {field.field_path}
                          </TableCell>
                          <TableCell>
                            <Badge variant="secondary" className="font-mono text-xs">
                              {field.field_type}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-muted-foreground text-sm">
                            {field.native_type || "-"}
                          </TableCell>
                          <TableCell>
                            <Badge
                              variant={
                                field.nullable === "true"
                                  ? "outline"
                                  : "default"
                              }
                              className="text-xs"
                            >
                              {field.nullable === "true" ? "Yes" : "No"}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-sm max-w-[300px] truncate">
                            {field.description || "-"}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                ) : (
                  <div className="flex items-center justify-center p-8">
                    <p className="text-muted-foreground">No schema fields defined</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Tags tab */}
          <TabsContent value="tags" className="mt-4">
            <Card>
              <CardContent className="pt-6">
                {dataset.tags.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {dataset.tags.map((tag) => (
                      <Badge
                        key={tag.id}
                        style={{ backgroundColor: tag.color, color: "#fff" }}
                        className="text-sm px-3 py-1"
                      >
                        {tag.name}
                      </Badge>
                    ))}
                  </div>
                ) : (
                  <p className="text-muted-foreground">No tags attached</p>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Owners tab */}
          <TabsContent value="owners" className="mt-4">
            <Card>
              <CardContent className="p-0">
                {dataset.owners.length > 0 ? (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Owner</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead>Added</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {dataset.owners.map((owner) => (
                        <TableRow key={owner.id}>
                          <TableCell className="font-medium">
                            {owner.owner_name}
                          </TableCell>
                          <TableCell>
                            <Badge variant="outline" className="text-xs">
                              {owner.owner_type.replace("_", " ")}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-muted-foreground text-sm">
                            {new Date(owner.created_at).toLocaleDateString()}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                ) : (
                  <div className="flex items-center justify-center p-8">
                    <p className="text-muted-foreground">No owners assigned</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Glossary terms tab */}
          <TabsContent value="glossary" className="mt-4">
            <Card>
              <CardContent className="p-0">
                {dataset.glossary_terms.length > 0 ? (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Term</TableHead>
                        <TableHead>Description</TableHead>
                        <TableHead>Source</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {dataset.glossary_terms.map((term) => (
                        <TableRow key={term.id}>
                          <TableCell className="font-medium">
                            {term.name}
                          </TableCell>
                          <TableCell className="text-sm max-w-[300px] truncate">
                            {term.description || "-"}
                          </TableCell>
                          <TableCell className="text-muted-foreground text-sm">
                            {term.source || "-"}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                ) : (
                  <div className="flex items-center justify-center p-8">
                    <p className="text-muted-foreground">
                      No glossary terms attached
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </>
  )
}
