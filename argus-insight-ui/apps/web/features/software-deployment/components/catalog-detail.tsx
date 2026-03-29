"use client"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@workspace/ui/components/card"
import { Badge } from "@workspace/ui/components/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@workspace/ui/components/table"
import type { PluginResponse, PluginVersionResponse } from "@/features/software-deployment/types"

interface CatalogDetailProps {
  plugin: PluginResponse
}

function statusVariant(status: PluginVersionResponse["status"]) {
  switch (status) {
    case "stable":
      return "default" as const
    case "beta":
      return "secondary" as const
    case "deprecated":
      return "destructive" as const
  }
}

function statusColor(status: PluginVersionResponse["status"]) {
  switch (status) {
    case "stable":
      return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
    case "beta":
      return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200"
    case "deprecated":
      return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200"
  }
}

export function CatalogDetail({ plugin }: CatalogDetailProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{plugin.display_name}</CardTitle>
        <CardDescription>{plugin.description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Tags */}
        {plugin.tags.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {plugin.tags.map((tag) => (
              <Badge key={tag} variant="outline">
                {tag}
              </Badge>
            ))}
          </div>
        )}

        {/* Dependencies */}
        <div className="text-sm">
          <span className="text-muted-foreground font-medium">Depends on: </span>
          {plugin.depends_on.length > 0
            ? plugin.depends_on.join(", ")
            : "No dependencies"}
        </div>

        {/* Provides */}
        <div className="text-sm">
          <span className="text-muted-foreground font-medium">Provides: </span>
          {plugin.provides.length > 0
            ? plugin.provides.join(", ")
            : "Nothing"}
        </div>

        {/* Requires */}
        <div className="text-sm">
          <span className="text-muted-foreground font-medium">Requires: </span>
          {plugin.requires.length > 0
            ? plugin.requires.join(", ")
            : "Nothing"}
        </div>

        {/* Versions Table */}
        {plugin.versions.length > 0 && (
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Version</TableHead>
                  <TableHead>Display Name</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Release Date</TableHead>
                  <TableHead>Changelog</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {plugin.versions.map((v) => (
                  <TableRow key={v.version}>
                    <TableCell className="font-mono text-sm">
                      {v.version}
                    </TableCell>
                    <TableCell>{v.display_name}</TableCell>
                    <TableCell>
                      <span
                        className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${statusColor(v.status)}`}
                      >
                        {v.status}
                      </span>
                    </TableCell>
                    <TableCell>
                      {v.release_date
                        ? new Date(v.release_date).toLocaleDateString()
                        : "-"}
                    </TableCell>
                    <TableCell
                      className="max-w-[300px] truncate"
                      title={v.changelog ?? undefined}
                    >
                      {v.changelog ?? "-"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
