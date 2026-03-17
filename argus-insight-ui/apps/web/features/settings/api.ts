const BASE = "/api/v1/infraconfig"
const SECURITY_BASE = "/api/v1/security"

// --------------------------------------------------------------------------- //
// Infrastructure Configuration
// --------------------------------------------------------------------------- //

export type InfraCategory = {
  category: string
  items: Record<string, string>
}

export type InfraConfig = {
  categories: InfraCategory[]
}

/**
 * Fetch all infrastructure configuration from the server.
 */
export async function fetchInfraConfig(): Promise<InfraConfig> {
  const res = await fetch(`${BASE}/configuration`)
  if (!res.ok) throw new Error(`Failed to fetch infra config: ${res.status}`)
  return res.json()
}

/**
 * Update settings within a single infrastructure category.
 */
export async function updateInfraCategory(
  category: string,
  items: Record<string, string>,
): Promise<void> {
  const res = await fetch(`${BASE}/configuration/category`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ category, items }),
  })
  if (!res.ok) throw new Error(`Failed to update infra category: ${res.status}`)
}

/**
 * Check if a file path exists on the server.
 */
export async function checkPath(path: string): Promise<boolean> {
  const res = await fetch(`${BASE}/check-path`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path }),
  })
  if (!res.ok) throw new Error(`Failed to check path: ${res.status}`)
  const data = await res.json()
  return data.exists
}

// --------------------------------------------------------------------------- //
// Security / CA Certificate Management
// --------------------------------------------------------------------------- //

export type CaCertStatus = {
  exists: boolean
  filename: string
  cert_path: string
}

export type CaCertViewData = {
  raw: string
  decoded: string
}

/**
 * Check the status of the CA certificate file.
 */
export async function fetchCaCertStatus(): Promise<CaCertStatus> {
  const res = await fetch(`${SECURITY_BASE}/ca/status`)
  if (!res.ok) throw new Error(`Failed to fetch CA cert status: ${res.status}`)
  return res.json()
}

/**
 * Upload a CA certificate file.
 */
export async function uploadCaCert(file: File): Promise<{ success: boolean; filename: string; path: string }> {
  const formData = new FormData()
  formData.append("file", file)
  const res = await fetch(`${SECURITY_BASE}/ca/upload`, {
    method: "POST",
    body: formData,
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({ detail: `Upload failed: ${res.status}` }))
    throw new Error(data.detail || `Upload failed: ${res.status}`)
  }
  return res.json()
}

/**
 * View the CA certificate content and decoded information.
 */
export async function viewCaCert(): Promise<CaCertViewData> {
  const res = await fetch(`${SECURITY_BASE}/ca/view`)
  if (!res.ok) {
    const data = await res.json().catch(() => ({ detail: `View failed: ${res.status}` }))
    throw new Error(data.detail || `View failed: ${res.status}`)
  }
  return res.json()
}

/**
 * Delete the CA certificate file.
 */
export async function deleteCaCert(): Promise<void> {
  const res = await fetch(`${SECURITY_BASE}/ca`, {
    method: "DELETE",
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({ detail: `Delete failed: ${res.status}` }))
    throw new Error(data.detail || `Delete failed: ${res.status}`)
  }
}

// --------------------------------------------------------------------------- //
// Security / CA Key Management
// --------------------------------------------------------------------------- //

export type CaKeyStatus = {
  exists: boolean
  filename: string
  cert_path: string
}

export type CaKeyViewData = {
  raw: string
  decoded: string
}

/**
 * Check the status of the CA key file.
 */
export async function fetchCaKeyStatus(): Promise<CaKeyStatus> {
  const res = await fetch(`${SECURITY_BASE}/ca-key/status`)
  if (!res.ok) throw new Error(`Failed to fetch CA key status: ${res.status}`)
  return res.json()
}

/**
 * Upload a CA key file.
 */
export async function uploadCaKey(file: File): Promise<{ success: boolean; filename: string; path: string }> {
  const formData = new FormData()
  formData.append("file", file)
  const res = await fetch(`${SECURITY_BASE}/ca-key/upload`, {
    method: "POST",
    body: formData,
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({ detail: `Upload failed: ${res.status}` }))
    throw new Error(data.detail || `Upload failed: ${res.status}`)
  }
  return res.json()
}

/**
 * View the CA key content and decoded information.
 */
export async function viewCaKey(): Promise<CaKeyViewData> {
  const res = await fetch(`${SECURITY_BASE}/ca-key/view`)
  if (!res.ok) {
    const data = await res.json().catch(() => ({ detail: `View failed: ${res.status}` }))
    throw new Error(data.detail || `View failed: ${res.status}`)
  }
  return res.json()
}

/**
 * Delete the CA key file.
 */
export async function deleteCaKey(): Promise<void> {
  const res = await fetch(`${SECURITY_BASE}/ca-key`, {
    method: "DELETE",
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({ detail: `Delete failed: ${res.status}` }))
    throw new Error(data.detail || `Delete failed: ${res.status}`)
  }
}

// --------------------------------------------------------------------------- //
// Self-Signed CA Generation
// --------------------------------------------------------------------------- //

export type GenerateSelfSignedCaParams = {
  country: string
  state: string
  locality: string
  organization: string
  org_unit: string
  common_name: string
  days: number
  key_bits: number
}

export type GenerateSelfSignedCaResult = {
  success: boolean
  cert_filename: string
  key_filename: string
  cert_path: string
  key_path: string
}

/**
 * Generate a self-signed CA certificate and key on the server.
 */
export async function generateSelfSignedCa(
  params: GenerateSelfSignedCaParams,
): Promise<GenerateSelfSignedCaResult> {
  const res = await fetch(`${SECURITY_BASE}/ca/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({ detail: `Generation failed: ${res.status}` }))
    throw new Error(data.detail || `Generation failed: ${res.status}`)
  }
  return res.json()
}
