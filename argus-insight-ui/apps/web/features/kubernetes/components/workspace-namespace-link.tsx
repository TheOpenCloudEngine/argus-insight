"use client"

import Link from "next/link"
import { ExternalLink } from "lucide-react"
import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"

interface WorkspaceNamespaceLinkProps {
  namespace: string
  workspaceName?: string
}

/**
 * Inline link component that connects a K8s namespace to its Argus workspace.
 * Shows "View in Kubernetes" or "View Workspace" depending on context.
 */
export function ViewInKubernetes({ namespace }: { namespace: string }) {
  if (!namespace) return null

  return (
    <Link
      href={`/dashboard/kubernetes/cluster/namespaces/${encodeURIComponent(namespace)}`}
      prefetch={false}
    >
      <Button variant="outline" size="sm" className="h-7 text-xs">
        <ExternalLink className="h-3 w-3 mr-1" />
        View in Kubernetes
      </Button>
    </Link>
  )
}

export function ViewWorkspace({ namespace, workspaceName }: WorkspaceNamespaceLinkProps) {
  if (!namespace) return null

  return (
    <Link
      href={`/dashboard/workspaces`}
      prefetch={false}
    >
      <Badge variant="outline" className="text-xs cursor-pointer hover:bg-muted">
        <ExternalLink className="h-2.5 w-2.5 mr-1" />
        Workspace: {workspaceName || namespace}
      </Badge>
    </Link>
  )
}

/**
 * For namespace detail pages, detect if the namespace is an Argus workspace
 * and show a link to the workspace management page.
 */
export function NamespaceWorkspaceDetector({ namespace }: { namespace: string }) {
  // Workspace namespaces follow the pattern: argus-ws-{name}
  const isWorkspaceNs = namespace.startsWith("argus-ws-")
  const workspaceName = isWorkspaceNs ? namespace.replace("argus-ws-", "") : null

  // App namespaces
  const isAppNs = namespace === "argus-apps"

  if (!isWorkspaceNs && !isAppNs) return null

  return (
    <div className="flex items-center gap-2 text-sm">
      {isWorkspaceNs && (
        <Badge variant="outline" className="bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20">
          Argus Workspace: {workspaceName}
        </Badge>
      )}
      {isAppNs && (
        <Badge variant="outline" className="bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20">
          Argus Apps Namespace
        </Badge>
      )}
      <Link href="/dashboard/workspaces" prefetch={false}>
        <Button variant="ghost" size="sm" className="h-6 text-xs">
          <ExternalLink className="h-3 w-3 mr-1" />
          View Workspaces
        </Button>
      </Link>
    </div>
  )
}
