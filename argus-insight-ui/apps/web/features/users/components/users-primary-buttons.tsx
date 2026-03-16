"use client"

import { Button } from "@workspace/ui/components/button"
import { useUsers } from "./users-provider"

export function UsersPrimaryButtons() {
  const { setOpen } = useUsers()

  return (
    <div className="flex gap-2">
      <Button onClick={() => setOpen("activate")}>
        Activate
      </Button>
      <Button onClick={() => setOpen("deactivate")}>
        Deactivate
      </Button>
      <Button onClick={() => setOpen("add")}>
        Add
      </Button>
    </div>
  )
}
