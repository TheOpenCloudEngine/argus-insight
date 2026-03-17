"use client"

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
}

export default function FileBrowserPage() {
  return (
    <>
      <DashboardHeader title="File Browser" />
      <div className="flex flex-1 flex-col gap-4 p-4">
        <ObjectStorageBrowser
          bucket="test"
          dataSource={dataSource}
        />
      </div>
    </>
  )
}
