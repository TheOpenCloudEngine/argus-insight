import type {
  FilesystemDataSource,
  FilesystemFile,
  FilesystemFolder,
  ListDirectoryResponse,
} from "@/components/local-filesystem-browser"

const API_BASE = "/api/v1/filesystem"

async function apiFetch<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init)
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(body.detail || `API error ${res.status}`)
  }
  return res.json()
}

/** Convert server folder response to UI type. */
function toFolder(f: {
  key: string
  name: string
  owner?: string
  group?: string
  permissions?: string
}): FilesystemFolder {
  return {
    kind: "folder",
    key: f.key,
    name: f.name,
    owner: f.owner,
    group: f.group,
    permissions: f.permissions,
  }
}

/** Convert server file response to UI type. */
function toFile(f: {
  key: string
  name: string
  size: number
  last_modified: string
  owner?: string
  group?: string
  permissions?: string
}): FilesystemFile {
  return {
    kind: "file",
    key: f.key,
    name: f.name,
    size: f.size,
    lastModified: f.last_modified,
    owner: f.owner,
    group: f.group,
    permissions: f.permissions,
  }
}

/** Create a FilesystemDataSource that talks to the catalog server. */
export function createFilesystemDataSource(): FilesystemDataSource {
  return {
    async listDirectory(path: string): Promise<ListDirectoryResponse> {
      const params = new URLSearchParams({ path })
      const data = await apiFetch<{
        folders: Array<{
          key: string
          name: string
          owner?: string
          group?: string
          permissions?: string
        }>
        files: Array<{
          key: string
          name: string
          size: number
          last_modified: string
          owner?: string
          group?: string
          permissions?: string
        }>
        current_path: string
      }>(`${API_BASE}/list?${params}`)

      return {
        folders: data.folders.map(toFolder),
        files: data.files.map(toFile),
        currentPath: data.current_path,
      }
    },

    async deletePaths(paths: string[]): Promise<void> {
      await apiFetch(`${API_BASE}/delete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ paths }),
      })
    },

    async createFolder(path: string): Promise<void> {
      await apiFetch(`${API_BASE}/folders`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path }),
      })
    },

    async uploadFiles(directoryPath: string, files: File[]): Promise<void> {
      for (const file of files) {
        const formData = new FormData()
        formData.append("file", file)
        const params = new URLSearchParams({ path: directoryPath })
        await apiFetch(`${API_BASE}/upload?${params}`, {
          method: "POST",
          body: formData,
        })
      }
    },

    async getDownloadUrl(path: string): Promise<string> {
      const params = new URLSearchParams({ path })
      return `${API_BASE}/download?${params}`
    },

    async renamePath(sourcePath: string, destinationPath: string): Promise<void> {
      await apiFetch(`${API_BASE}/rename`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_path: sourcePath,
          destination_path: destinationPath,
        }),
      })
    },

    async previewFile(
      path: string,
      options?: { sheet?: string; maxRows?: number },
    ): Promise<unknown> {
      const params = new URLSearchParams({ path })
      if (options?.sheet) params.set("sheet", options.sheet)
      if (options?.maxRows) params.set("max_rows", String(options.maxRows))
      return apiFetch(`${API_BASE}/preview?${params}`)
    },
  }
}
