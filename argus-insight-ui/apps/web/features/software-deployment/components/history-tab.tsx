"use client"

import { useEffect, useState } from "react"
import {
  CheckCircle2,
  Circle,
  Loader2,
  SkipForward,
  XCircle,
} from "lucide-react"
import { Badge } from "@workspace/ui/components/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@workspace/ui/components/table"
import type {
  StepExecution,
  WorkflowExecution,
} from "@/features/software-deployment/types"
import { fetchAllWorkflows } from "@/features/software-deployment/api"

function statusBadge(status: WorkflowExecution["status"]) {
  switch (status) {
    case "completed":
      return (
        <Badge className="bg-green-100 text-green-800 hover:bg-green-100 dark:bg-green-900 dark:text-green-200">
          completed
        </Badge>
      )
    case "failed":
      return (
        <Badge className="bg-red-100 text-red-800 hover:bg-red-100 dark:bg-red-900 dark:text-red-200">
          failed
        </Badge>
      )
    case "running":
      return (
        <Badge className="animate-pulse bg-blue-100 text-blue-800 hover:bg-blue-100 dark:bg-blue-900 dark:text-blue-200">
          running
        </Badge>
      )
    case "pending":
    case "cancelled":
      return (
        <Badge className="bg-gray-100 text-gray-800 hover:bg-gray-100 dark:bg-gray-800 dark:text-gray-200">
          {status}
        </Badge>
      )
  }
}

function stepIcon(status: StepExecution["status"]) {
  switch (status) {
    case "completed":
      return <CheckCircle2 className="h-4 w-4 text-green-600" />
    case "failed":
      return <XCircle className="h-4 w-4 text-red-600" />
    case "running":
      return <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
    case "skipped":
      return <SkipForward className="h-4 w-4 text-gray-400" />
    case "pending":
      return <Circle className="h-4 w-4 text-gray-400" />
  }
}

function formatDuration(step: StepExecution): string {
  if (!step.started_at || !step.finished_at) return "-"
  const start = new Date(step.started_at).getTime()
  const end = new Date(step.finished_at).getTime()
  const diffMs = end - start
  if (diffMs < 1000) return `${diffMs}ms`
  const secs = Math.floor(diffMs / 1000)
  if (secs < 60) return `${secs}s`
  const mins = Math.floor(secs / 60)
  const remainSecs = secs % 60
  return `${mins}m ${remainSecs}s`
}

function completedStepCount(workflow: WorkflowExecution): string {
  const completed = workflow.steps.filter(
    (s) => s.status === "completed",
  ).length
  return `${completed}/${workflow.steps.length}`
}

export function HistoryTab() {
  const [workflows, setWorkflows] = useState<WorkflowExecution[]>([])
  const [loading, setLoading] = useState(true)
  const [expandedId, setExpandedId] = useState<number | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchAllWorkflows()
      .then((data) => {
        if (!cancelled) setWorkflows(data)
      })
      .catch(() => {
        if (!cancelled) setWorkflows([])
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="text-muted-foreground h-6 w-6 animate-spin" />
        <span className="text-muted-foreground ml-2 text-sm">
          Loading workflow history...
        </span>
      </div>
    )
  }

  if (workflows.length === 0) {
    return (
      <div className="text-muted-foreground py-12 text-center text-sm">
        No workflow executions found.
      </div>
    )
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-[60px]">ID</TableHead>
            <TableHead className="w-[100px]">Workspace ID</TableHead>
            <TableHead>Workflow</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="text-center">Steps</TableHead>
            <TableHead>Created At</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {workflows.map((wf) => (
            <tbody key={wf.id}>
              <TableRow
                className={`cursor-pointer ${expandedId === wf.id ? "bg-muted/50" : ""}`}
                onClick={() =>
                  setExpandedId(expandedId === wf.id ? null : wf.id)
                }
              >
                <TableCell className="font-mono text-sm">{wf.id}</TableCell>
                <TableCell>{wf.workspace_id}</TableCell>
                <TableCell className="font-medium">
                  {wf.workflow_name}
                </TableCell>
                <TableCell>{statusBadge(wf.status)}</TableCell>
                <TableCell className="text-center">
                  {completedStepCount(wf)}
                </TableCell>
                <TableCell>
                  {new Date(wf.created_at).toLocaleString()}
                </TableCell>
              </TableRow>

              {/* Expanded Step Details */}
              {expandedId === wf.id && (
                <TableRow>
                  <TableCell colSpan={6} className="bg-muted/30 p-4">
                    <div className="space-y-2">
                      <h4 className="text-sm font-semibold">Step Details</h4>
                      <ol className="space-y-1.5">
                        {wf.steps
                          .sort((a, b) => a.step_order - b.step_order)
                          .map((step) => (
                            <li
                              key={step.id}
                              className="flex items-center gap-3 text-sm"
                            >
                              {stepIcon(step.status)}
                              <span className="min-w-[200px] font-medium">
                                {step.step_name}
                              </span>
                              <span className="text-muted-foreground min-w-[80px]">
                                {formatDuration(step)}
                              </span>
                              {step.status === "failed" &&
                                step.error_message && (
                                  <span className="text-xs text-red-600">
                                    {step.error_message}
                                  </span>
                                )}
                            </li>
                          ))}
                      </ol>
                    </div>
                  </TableCell>
                </TableRow>
              )}
            </tbody>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
