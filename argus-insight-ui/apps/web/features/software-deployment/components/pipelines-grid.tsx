"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { Copy, Loader2, MoreHorizontal, Trash2 } from "lucide-react"
import { AgGridReact } from "ag-grid-react"
import {
  AllCommunityModule,
  ModuleRegistry,
  type ColDef,
  type PaginationNumberFormatterParams,
} from "ag-grid-community"

import { Button } from "@workspace/ui/components/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@workspace/ui/components/dropdown-menu"

import type { PipelineResponse } from "@/features/software-deployment/types"
import {
  clonePipeline,
  deletePipeline,
  fetchPipelines,
} from "@/features/software-deployment/api"

ModuleRegistry.registerModules([AllCommunityModule])

function formatDateTime(value: string): string {
  const d = new Date(value)
  const pad = (n: number) => String(n).padStart(2, "0")
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

interface PipelinesGridProps {
  onSelect: (pipeline: PipelineResponse) => void
  onDeleted: (pipelineId: number) => void
  refreshKey: number
}

export function PipelinesGrid({ onSelect, onDeleted, refreshKey }: PipelinesGridProps) {
  const [pipelines, setPipelines] = useState<PipelineResponse[]>([])
  const [loading, setLoading] = useState(true)

  // Confirm dialog state
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [confirmAction, setConfirmAction] = useState<"delete" | "clone">("delete")
  const [confirmTarget, setConfirmTarget] = useState<PipelineResponse | null>(null)
  const [actionLoading, setActionLoading] = useState(false)

  const loadPipelines = useCallback(async (showLoading = true) => {
    try {
      if (showLoading) setLoading(true)
      const data = await fetchPipelines()
      setPipelines(data.items)
    } catch {
      setPipelines([])
    } finally {
      if (showLoading) setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadPipelines()
  }, [loadPipelines, refreshKey])

  const openConfirm = useCallback(
    (action: "delete" | "clone", pipeline: PipelineResponse) => {
      setConfirmAction(action)
      setConfirmTarget(pipeline)
      setConfirmOpen(true)
    },
    [],
  )

  const handleConfirm = useCallback(async () => {
    if (!confirmTarget) return
    setActionLoading(true)
    try {
      if (confirmAction === "delete") {
        await deletePipeline(confirmTarget.id)
        onDeleted(confirmTarget.id)
      } else {
        await clonePipeline(confirmTarget.id)
      }
      await loadPipelines(false)
    } catch {
      // ignore
    } finally {
      setActionLoading(false)
      setConfirmOpen(false)
      setConfirmTarget(null)
    }
  }, [confirmAction, confirmTarget, loadPipelines, onDeleted])

  const columnDefs = useMemo<ColDef<PipelineResponse>[]>(
    () => [
      {
        headerName: "Name",
        field: "display_name",
        flex: 1,
        minWidth: 130,
      },
      {
        headerName: "Description",
        field: "description",
        flex: 2,
        minWidth: 200,
      },
      {
        headerName: "Plugins",
        valueGetter: (params) => params.data?.plugins?.length ?? 0,
        width: 100,
        cellStyle: { textAlign: "center" },
      },
      {
        headerName: "Version",
        field: "version",
        width: 90,
        cellStyle: { textAlign: "center" },
      },
      {
        headerName: "Owner",
        field: "created_by",
        width: 120,
      },
      {
        headerName: "Created",
        field: "created_at",
        width: 160,
        valueFormatter: (params) =>
          params.value ? formatDateTime(params.value) : "",
      },
      {
        headerName: "Updated",
        field: "updated_at",
        width: 160,
        valueFormatter: (params) =>
          params.value ? formatDateTime(params.value) : "",
      },
      {
        headerName: "Action",
        width: 80,
        sortable: false,
        filter: false,
        cellRenderer: (params: { data: PipelineResponse }) => (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                onClick={(e) => e.stopPropagation()}
              >
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem
                onClick={(e) => {
                  e.stopPropagation()
                  openConfirm("clone", params.data)
                }}
              >
                <Copy className="h-4 w-4 mr-2" />
                Clone
              </DropdownMenuItem>
              <DropdownMenuItem
                className="text-destructive"
                onClick={(e) => {
                  e.stopPropagation()
                  openConfirm("delete", params.data)
                }}
              >
                <Trash2 className="h-4 w-4 mr-2" />
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        ),
      },
    ],
    [openConfirm],
  )

  return (
    <>
      <div className="ag-theme-alpine" style={{ width: "100%", height: 36 + 40 * 10 + 48 }}>
        <style>{`
          .ag-theme-alpine {
            --ag-font-family: 'Roboto Condensed', Roboto, sans-serif;
            --ag-font-size: var(--text-sm);
          }
        `}</style>
        <AgGridReact<PipelineResponse>
          rowData={pipelines}
          columnDefs={columnDefs}
          loading={loading}
          rowSelection="single"
          overlayNoRowsTemplate="No saved pipelines."
          onRowClicked={(event) => {
            if (event.data) onSelect(event.data)
          }}
          getRowId={(params) => String(params.data.id)}
          headerHeight={36}
          rowHeight={40}
          pagination={true}
          paginationPageSize={10}
          paginationPageSizeSelector={[10, 20, 50]}
          paginationNumberFormatter={(
            params: PaginationNumberFormatterParams,
          ) => params.value.toLocaleString()}
        />
      </div>

      {/* Confirm Dialog */}
      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>
              {confirmAction === "delete"
                ? "Delete Pipeline"
                : "Clone Pipeline"}
            </DialogTitle>
            <DialogDescription>
              {confirmAction === "delete"
                ? "Are you sure you want to delete the selected pipeline?"
                : "Are you sure you want to clone the selected pipeline?"}
            </DialogDescription>
          </DialogHeader>
          {confirmTarget && (
            <p className="text-sm font-medium py-2">
              {confirmTarget.display_name}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              onClick={() => setConfirmOpen(false)}
              disabled={actionLoading}
            >
              Cancel
            </Button>
            <Button
              variant={confirmAction === "delete" ? "destructive" : "default"}
              onClick={handleConfirm}
              disabled={actionLoading}
            >
              {actionLoading ? (
                <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
              ) : confirmAction === "delete" ? (
                <Trash2 className="h-4 w-4 mr-1.5" />
              ) : (
                <Copy className="h-4 w-4 mr-1.5" />
              )}
              {confirmAction === "delete" ? "Delete" : "Clone"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}
