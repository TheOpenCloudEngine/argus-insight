"use client"

import { useCallback, useEffect, useState } from "react"
import { Loader2 } from "lucide-react"

import { DashboardHeader } from "@/components/dashboard-header"
import { ObjectStorageBrowser } from "@/components/object-storage-browser"
import type { BrowserDataSource } from "@/components/object-storage-browser"
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
import type { BucketInfo } from "@/features/object-storage/api"

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
  const [buckets, setBuckets] = useState<BucketInfo[]>([])
  const [selectedBucket, setSelectedBucket] = useState<string | null>(null)
  const [currentUsername, setCurrentUsername] = useState<string | null>(null)

  const initialize = useCallback(async () => {
    try {
      setInitializing(true)
      setError(null)

      // 1. Fetch current user info
      const meRes = await fetch("/api/v1/auth/me")
      const me = meRes.ok ? await meRes.json() : null
      const username: string = me?.username ?? "unknown"
      setCurrentUsername(username)

      // 2. Ensure user-<USERNAME> buckets exist for all users
      await ensureUserBuckets()

      // 3. Fetch bucket list
      const bucketData = await listBuckets()
      const allBuckets = bucketData.buckets

      // 4. Filter: show user-<my USERNAME> and non-user-* buckets
      const myUserBucket = `user-${username}`
      const filtered = allBuckets.filter(
        (b) => b.name === myUserBucket || !b.name.startsWith("user-")
      )
      setBuckets(filtered)

      // 5. Auto-select user's own bucket if available
      if (filtered.some((b) => b.name === myUserBucket)) {
        setSelectedBucket(myUserBucket)
      } else if (filtered.length > 0) {
        setSelectedBucket(filtered[0].name)
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
        {/* Bucket selector */}
        <div className="flex items-center gap-3">
          <label className="text-sm font-medium text-muted-foreground whitespace-nowrap">
            Bucket
          </label>
          <div className="flex flex-wrap gap-1.5">
            {buckets.map((b) => (
              <button
                key={b.name}
                onClick={() => setSelectedBucket(b.name)}
                className={`inline-flex items-center rounded-md border px-3 py-1.5 text-sm font-medium transition-colors ${
                  selectedBucket === b.name
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-border bg-background text-foreground hover:bg-accent hover:text-accent-foreground"
                }`}
              >
                {b.name}
              </button>
            ))}
          </div>
        </div>

        {/* Object storage browser */}
        {selectedBucket && (
          <ObjectStorageBrowser
            key={selectedBucket}
            bucket={selectedBucket}
            dataSource={dataSource}
          />
        )}
      </div>
    </>
  )
}
