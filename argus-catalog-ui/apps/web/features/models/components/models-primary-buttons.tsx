"use client"

import { Trash2 } from "lucide-react"
import { Button } from "@workspace/ui/components/button"
import { useModels } from "./models-provider"

export function ModelsPrimaryButtons() {
  const { setOpen, selectedNames, setDeleteTargetNames } = useModels()

  return (
    <Button
      size="sm"
      variant="destructive"
      disabled={selectedNames.length === 0}
      onClick={() => {
        setDeleteTargetNames(selectedNames)
        setOpen("delete")
      }}
    >
      <Trash2 className="mr-1 h-4 w-4" />
      Delete Models
    </Button>
  )
}
