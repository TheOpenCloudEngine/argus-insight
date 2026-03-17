"use client"

import { useEffect } from "react"
import { useParams, useRouter } from "next/navigation"
import { ArrowLeft } from "lucide-react"
import { Button } from "@workspace/ui/components/button"
import { DashboardHeader } from "@/components/dashboard-header"
import { NotesProvider, useNotes } from "@/features/notes/components/notes-provider"
import { SectionTabs } from "@/features/notes/components/section-tabs"
import { PageList } from "@/features/notes/components/page-list"
import { PageEditor } from "@/features/notes/components/page-editor"
import { fetchNotebook } from "@/features/notes/api"

function NotebookDetail() {
  const params = useParams()
  const router = useRouter()
  const notebookId = Number(params.notebookId)
  const { currentNotebook, selectNotebook } = useNotes()

  useEffect(() => {
    if (!notebookId || currentNotebook?.id === notebookId) return
    fetchNotebook(notebookId).then((nb) => selectNotebook(nb))
  }, [notebookId, currentNotebook?.id, selectNotebook])

  return (
    <>
      <DashboardHeader
        title={currentNotebook?.title ?? "Loading..."}
      />
      <div className="flex flex-col flex-1 min-h-0">
        <div className="flex items-center gap-2 px-2 pt-1">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 text-sm"
            onClick={() => router.push("/dashboard/notes")}
          >
            <ArrowLeft className="h-3.5 w-3.5 mr-1" />
            Notebooks
          </Button>
        </div>
        <SectionTabs />
        <div className="flex flex-1 min-h-0">
          <PageList />
          <div className="flex-1 min-w-0">
            <PageEditor />
          </div>
        </div>
      </div>
    </>
  )
}

export default function NotebookDetailPage() {
  return (
    <NotesProvider>
      <NotebookDetail />
    </NotesProvider>
  )
}
