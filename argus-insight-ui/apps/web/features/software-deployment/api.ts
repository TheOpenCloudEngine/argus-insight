import { authFetch } from "@/features/auth/auth-fetch"
import type {
  JsonSchema,
  PipelineCreateRequest,
  PipelineListResponse,
  PipelineResponse,
  PluginOrderItem,
  PluginOrderValidateResponse,
  PluginRescanResponse,
  PluginResponse,
  WorkflowExecution,
} from "./types"

const PLUGIN_BASE = "/api/v1/plugins"
const WORKSPACE_BASE = "/api/v1/workspace"

// ---------------------------------------------------------------------------
// Error helpers
// ---------------------------------------------------------------------------

async function extractError(res: Response, fallback: string): Promise<string> {
  if (res.status === 502)
    return "서버에 연결할 수 없습니다. argus-insight-server가 실행 중인지 확인하세요."
  if (res.status === 503) return "서비스를 사용할 수 없습니다."
  try {
    const data = await res.json()
    if (data.detail) {
      if (typeof data.detail === "string") return data.detail
      if (data.detail.violations) return data.detail.violations.join("\n")
    }
  } catch {
    // ignore
  }
  return `${fallback}: ${res.status}`
}

// ---------------------------------------------------------------------------
// Plugin Catalog
// ---------------------------------------------------------------------------

export async function fetchPlugins(): Promise<PluginResponse[]> {
  const res = await authFetch(PLUGIN_BASE)
  if (!res.ok) throw new Error(await extractError(res, "Failed to fetch plugins"))
  return res.json()
}

export async function fetchPlugin(name: string): Promise<PluginResponse> {
  const res = await authFetch(`${PLUGIN_BASE}/${name}`)
  if (!res.ok) throw new Error(await extractError(res, "Failed to fetch plugin"))
  return res.json()
}

export async function fetchPluginVersionSchema(
  name: string,
  version: string,
): Promise<JsonSchema | null> {
  const res = await authFetch(`${PLUGIN_BASE}/${name}/versions/${version}/schema`)
  if (!res.ok) return null
  const data = await res.json()
  if (data.message) return null // "No configurable settings"
  return data
}

export async function rescanPlugins(): Promise<PluginRescanResponse> {
  const res = await authFetch(`${PLUGIN_BASE}/rescan`, { method: "POST" })
  if (!res.ok) throw new Error(await extractError(res, "Failed to rescan plugins"))
  return res.json()
}

// ---------------------------------------------------------------------------
// Pipeline Order
// ---------------------------------------------------------------------------

export async function updatePluginOrder(plugins: PluginOrderItem[]): Promise<void> {
  const res = await authFetch(`${PLUGIN_BASE}/order`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ plugins }),
  })
  if (!res.ok) throw new Error(await extractError(res, "Failed to save pipeline"))
}

export async function validatePluginOrder(
  pluginNames: string[],
  versions?: Record<string, string>,
): Promise<PluginOrderValidateResponse> {
  const res = await authFetch(`${PLUGIN_BASE}/validate-order`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ plugin_names: pluginNames, versions }),
  })
  if (!res.ok) throw new Error(await extractError(res, "Validation failed"))
  return res.json()
}

// ---------------------------------------------------------------------------
// Named Pipelines
// ---------------------------------------------------------------------------

export async function fetchPipelines(): Promise<PipelineListResponse> {
  const res = await authFetch(`${PLUGIN_BASE}/pipelines`)
  if (!res.ok) throw new Error(await extractError(res, "Failed to fetch pipelines"))
  return res.json()
}

export async function createPipeline(req: PipelineCreateRequest): Promise<PipelineResponse> {
  const res = await authFetch(`${PLUGIN_BASE}/pipelines`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  })
  if (!res.ok) throw new Error(await extractError(res, "Failed to create pipeline"))
  return res.json()
}

export async function updatePipeline(
  pipelineId: number,
  req: { display_name?: string; description?: string; plugins?: PluginOrderItem[] },
): Promise<PipelineResponse> {
  const res = await authFetch(`${PLUGIN_BASE}/pipelines/${pipelineId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  })
  if (!res.ok) throw new Error(await extractError(res, "Failed to update pipeline"))
  return res.json()
}

export async function clonePipeline(pipelineId: number): Promise<PipelineResponse> {
  const res = await authFetch(`${PLUGIN_BASE}/pipelines/${pipelineId}/clone`, {
    method: "POST",
  })
  if (!res.ok) throw new Error(await extractError(res, "Failed to clone pipeline"))
  return res.json()
}

export async function deletePipeline(pipelineId: number): Promise<void> {
  const res = await authFetch(`${PLUGIN_BASE}/pipelines/${pipelineId}`, {
    method: "DELETE",
  })
  if (!res.ok) throw new Error(await extractError(res, "Failed to delete pipeline"))
}

// ---------------------------------------------------------------------------
// Execution History
// ---------------------------------------------------------------------------

export async function fetchAllWorkflows(): Promise<WorkflowExecution[]> {
  // Fetch all workspaces, then get workflows for each
  const wsRes = await authFetch(`${WORKSPACE_BASE}/workspaces?page_size=100`)
  if (!wsRes.ok) return []
  const wsData = await wsRes.json()

  const results: WorkflowExecution[] = []
  for (const ws of wsData.items ?? []) {
    try {
      const wfRes = await authFetch(`${WORKSPACE_BASE}/workspaces/${ws.id}/workflow`)
      if (wfRes.ok) {
        const workflows: WorkflowExecution[] = await wfRes.json()
        results.push(...workflows)
      }
    } catch {
      // skip
    }
  }

  return results.sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  )
}
