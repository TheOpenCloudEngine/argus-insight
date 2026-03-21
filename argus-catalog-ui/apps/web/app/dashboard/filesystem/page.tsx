"use client"

import { useMemo } from "react"
import { DashboardHeader } from "@/components/dashboard-header"
import { LocalFilesystemBrowser } from "@/components/local-filesystem-browser"
import { createFilesystemDataSource } from "@/features/filesystem/api"

export default function FilesystemPage() {
  const dataSource = useMemo(() => createFilesystemDataSource(), [])

  return (
    <>
      <DashboardHeader title="File Browser" />
      <div className="flex flex-1 flex-col gap-4 p-4">
        <LocalFilesystemBrowser
          initialPath="/"
          dataSource={dataSource}
          className="flex-1"
        />
      </div>
    </>
  )
}
