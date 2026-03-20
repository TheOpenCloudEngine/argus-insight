const BASE = "/api/v1/settings"
const SECURITY_BASE = "/api/v1/security"

// --------------------------------------------------------------------------- //
// Error helpers
// --------------------------------------------------------------------------- //

async function extractErrorMessage(res: Response, fallback: string): Promise<string> {
  if (res.status === 502) {
    return "서버에 연결할 수 없습니다. argus-insight-server가 실행 중인지 확인하세요."
  }
  if (res.status === 503) {
    try {
      const data = await res.json()
      return data.detail || "서비스를 사용할 수 없습니다."
    } catch {
      return "서비스를 사용할 수 없습니다."
    }
  }
  try {
    const data = await res.json()
    if (data.detail) return data.detail
  } catch {
    // ignore parse errors
  }
  return `${fallback}: ${res.status}`
}

// --------------------------------------------------------------------------- //
// Infrastructure Configuration (per-category helpers)
// --------------------------------------------------------------------------- //

type InfraCategory = {
  category: string
  items: Record<string, string>
}

type InfraConfig = {
  categories: InfraCategory[]
}

/**
 * Internal: fetch all categories and return items for a specific category.
 */
async function fetchCategory(category: string): Promise<Record<string, string>> {
  const res = await fetch(`${BASE}/configuration`)
  if (!res.ok) throw new Error(await extractErrorMessage(res, `Failed to fetch ${category} config`))
  const data: InfraConfig = await res.json()
  const cat = data.categories.find((c) => c.category === category)
  return cat?.items ?? {}
}

/**
 * Internal: update items for a specific category.
 */
async function updateCategory(
  category: string,
  items: Record<string, string>,
): Promise<void> {
  const res = await fetch(`${BASE}/configuration/category`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ category, items }),
  })
  if (!res.ok) throw new Error(await extractErrorMessage(res, `Failed to update ${category} config`))
}

// --------------------------------------------------------------------------- //
// Domain Settings
// --------------------------------------------------------------------------- //

export async function fetchDomainConfig(): Promise<Record<string, string>> {
  return fetchCategory("domain")
}

export async function updateDomainConfig(items: Record<string, string>): Promise<void> {
  return updateCategory("domain", items)
}

// --------------------------------------------------------------------------- //
// PowerDNS Settings
// --------------------------------------------------------------------------- //

export async function fetchPowerDnsConfig(): Promise<Record<string, string>> {
  return fetchCategory("domain")
}

export async function updatePowerDnsConfig(items: Record<string, string>): Promise<void> {
  return updateCategory("domain", items)
}

// --------------------------------------------------------------------------- //
// LDAP Settings
// --------------------------------------------------------------------------- //

export async function fetchLdapConfig(): Promise<Record<string, string>> {
  return fetchCategory("ldap")
}

export async function updateLdapConfig(items: Record<string, string>): Promise<void> {
  return updateCategory("ldap", items)
}

// --------------------------------------------------------------------------- //
// Command Settings
// --------------------------------------------------------------------------- //

export async function fetchCommandConfig(): Promise<Record<string, string>> {
  return fetchCategory("command")
}

export async function updateCommandConfig(items: Record<string, string>): Promise<void> {
  return updateCategory("command", items)
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
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Failed to check path"))
  const data = await res.json()
  return data.exists
}

// --------------------------------------------------------------------------- //
// Security Settings (infra config)
// --------------------------------------------------------------------------- //

export async function fetchSecurityConfig(): Promise<Record<string, string>> {
  return fetchCategory("security")
}

export async function updateSecurityConfig(items: Record<string, string>): Promise<void> {
  return updateCategory("security", items)
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

// --------------------------------------------------------------------------- //
// Argus Settings
// --------------------------------------------------------------------------- //

export async function fetchArgusConfig(): Promise<Record<string, string>> {
  return fetchCategory("argus")
}

export async function updateArgusConfig(items: Record<string, string>): Promise<void> {
  return updateCategory("argus", items)
}

export async function testUnityCatalog(
  url: string,
  accessToken: string,
): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${BASE}/unity-catalog/test`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, access_token: accessToken }),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({ detail: `Test failed: ${res.status}` }))
    throw new Error(data.detail || `Test failed: ${res.status}`)
  }
  return res.json()
}

export async function initializeUnityCatalog(
  url: string,
  accessToken: string,
): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${BASE}/unity-catalog/initialize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, access_token: accessToken }),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({ detail: `Initialize failed: ${res.status}` }))
    throw new Error(data.detail || `Initialize failed: ${res.status}`)
  }
  return res.json()
}

export async function testObjectStorage(
  endpoint: string,
  accessKey: string,
  secretKey: string,
  region: string,
): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${BASE}/object-storage/test`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ endpoint, access_key: accessKey, secret_key: secretKey, region }),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({ detail: `Test failed: ${res.status}` }))
    throw new Error(data.detail || `Test failed: ${res.status}`)
  }
  return res.json()
}

export async function initializeObjectStorage(
  endpoint: string,
  accessKey: string,
  secretKey: string,
  region: string,
): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${BASE}/object-storage/initialize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ endpoint, access_key: accessKey, secret_key: secretKey, region }),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({ detail: `Initialize failed: ${res.status}` }))
    throw new Error(data.detail || `Initialize failed: ${res.status}`)
  }
  return res.json()
}

export async function testPrometheus(
  host: string,
  port: string,
): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${BASE}/prometheus/test`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ host, port: parseInt(port, 10) }),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({ detail: `Test failed: ${res.status}` }))
    throw new Error(data.detail || `Test failed: ${res.status}`)
  }
  return res.json()
}

export async function testDockerRegistry(
  url: string,
  username: string,
  password: string,
): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${BASE}/docker-registry/test`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, username, password }),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({ detail: `Test failed: ${res.status}` }))
    throw new Error(data.detail || `Test failed: ${res.status}`)
  }
  return res.json()
}
