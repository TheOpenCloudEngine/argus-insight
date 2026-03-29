"use client"

import { useCallback, useEffect, useState } from "react"
import { Loader2 } from "lucide-react"

import { DashboardHeader } from "@/components/dashboard-header"
import { ObjectStorageBrowser } from "@/components/object-storage-browser"
import type { BrowserDataSource } from "@/components/object-storage-browser"
import { authFetch } from "@/features/auth/auth-fetch"
import {
  listObjects,
  deleteObjects,
  createFolder,
  uploadFiles,
  uploadFileWithProgress,
  getDownloadUrl,
  copyObject,
  previewFile,
  fetchFilebrowserConfig,
  listBuckets,
  ensureUserBuckets,
} from "@/features/object-storage/api"

const dataSource: BrowserDataSource = {
  listObjects,
  deleteObjects,
  createFolder,
  uploadFiles,
  uploadFileWithProgress,
  getDownloadUrl,
  copyObject,
  previewFile,
  fetchConfiguration: fetchFilebrowserConfig,
}

export default function FileBrowserPage() {
  const [initializing, setInitializing] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [bucketNames, setBucketNames] = useState<string[]>([])
  const [selectedBucket, setSelectedBucket] = useState<string | null>(null)

  const initialize = useCallback(async () => {
    try {
      setInitializing(true)
      setError(null)

      // 1. Fetch current user info
      const meRes = await authFetch("/api/v1/auth/me")
      const me = meRes.ok ? await meRes.json() : null
      const username: string = me?.username ?? "unknown"
      const isAdmin: boolean = me?.is_admin ?? false

      // 2. Fetch bucket list
      const bucketData = await listBuckets()
      const allBuckets = bucketData.buckets

      // 3. Ensure user bucket exists only if missing
      const myUserBucket = `user-${username}`
      if (!allBuckets.some((b) => b.name === myUserBucket)) {
        await ensureUserBuckets()
        const refreshed = await listBuckets()
        allBuckets.length = 0
        allBuckets.push(...refreshed.buckets)
      }

      // 4. Filter buckets by role
      //    Admin: all buckets visible
      //    User: only own bucket (user-{username})
      const filtered = isAdmin
        ? allBuckets.map((b) => b.name)
        : allBuckets.filter((b) => b.name === myUserBucket).map((b) => b.name)
      setBucketNames(filtered)

      // 5. Auto-select user's own bucket if available
      if (filtered.includes(myUserBucket)) {
        setSelectedBucket(myUserBucket)
      } else if (filtered.length > 0) {
        setSelectedBucket(filtered[0])
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to initialize File Browser")
    } finally {
      setInitializing(false)
    }
  }, [])

  useEffect(() => {
    initialize()
  }, [initialize])

  const handleBucketChange = useCallback((bucket: string) => {
    setSelectedBucket(bucket)
  }, [])

  if (initializing) {
    return (
      <>
        <DashboardHeader title="File Browser" />
        <div className="flex flex-1 items-center justify-center p-4">
          <div className="flex items-center gap-2 text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin" />
            <span>Initializing File Browser...</span>
          </div>
        </div>
      </>
    )
  }

  if (error) {
    return (
      <>
        <DashboardHeader title="File Browser" />
        <div className="flex flex-1 items-center justify-center p-4">
          <div className="rounded-md bg-red-50 px-4 py-3 text-sm text-red-800 dark:bg-red-950 dark:text-red-200">
            {error}
          </div>
        </div>
      </>
    )
  }

  return (
    <>
      <DashboardHeader title="File Browser" />
      <div className="flex flex-1 flex-col gap-4 p-4">
        {selectedBucket && (
          <ObjectStorageBrowser
            key={selectedBucket}
            bucket={selectedBucket}
            dataSource={dataSource}
            buckets={bucketNames}
            onBucketChange={handleBucketChange}
          />
        )}
      </div>
    </>
  )
}
