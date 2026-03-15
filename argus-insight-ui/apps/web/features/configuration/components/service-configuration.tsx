"use client"

import { useRef, useState } from "react"
import { Save, Search } from "lucide-react"
import { Button } from "@workspace/ui/components/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"
import { Input } from "@workspace/ui/components/input"
import { ConfigField, type ConfigFieldHandle, type ConfigItem } from "./config-field"
import configData from "@/data/service-configuration.json"

type ConfigData = Record<string, ConfigItem[]>

const data = configData as ConfigData

export function ServiceConfiguration() {
  const [search, setSearch] = useState("")
  const [dialogOpen, setDialogOpen] = useState(false)
  const [jsonResult, setJsonResult] = useState("")

  // flatten all items across services
  const allItems: ConfigItem[] = Object.values(data).flat()

  const fieldRefs = useRef<Map<string, ConfigFieldHandle>>(new Map())

  const setRef = (key: string) => (handle: ConfigFieldHandle | null) => {
    if (handle) {
      fieldRefs.current.set(key, handle)
    } else {
      fieldRefs.current.delete(key)
    }
  }

  const handleSave = () => {
    const result: Record<string, unknown> = {}
    for (const item of allItems) {
      const handle = fieldRefs.current.get(item.key)
      if (handle) {
        result[item.key] = handle.getValue()
      }
    }
    setJsonResult(JSON.stringify(result, null, 2))
    setDialogOpen(true)
  }

  const filteredItems = allItems.filter((item) => {
    if (!search.trim()) return true
    const q = search.toLowerCase()
    return (
      item.name.toLowerCase().includes(q) ||
      item.key.toLowerCase().includes(q) ||
      item.description?.toLowerCase().includes(q)
    )
  })

  return (
    <div className="flex flex-col gap-4">
      {/* toolbar */}
      <div className="flex items-center justify-between gap-4">
        <div className="relative w-[36rem]">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            placeholder="설정 검색..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-8 h-8 text-sm"
          />
        </div>
        <Button size="sm" className="gap-1.5" onClick={handleSave}>
          <Save className="h-3.5 w-3.5" />
          변경사항 저장
        </Button>
      </div>

      {/* config items */}
      {filteredItems.length === 0 ? (
        <p className="text-sm text-muted-foreground py-8 text-center">검색 결과가 없습니다.</p>
      ) : (
        <div className="rounded-lg bg-card">
          {filteredItems.map((item) => (
            <ConfigField key={item.key} ref={setRef(item.key)} item={item} />
          ))}
        </div>
      )}

      {/* JSON result dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh] flex flex-col">
          <DialogHeader>
            <DialogTitle>변경사항 저장</DialogTitle>
          </DialogHeader>
          <pre className="flex-1 overflow-auto rounded-md bg-muted p-4 text-xs font-mono leading-relaxed">
            {jsonResult}
          </pre>
        </DialogContent>
      </Dialog>
    </div>
  )
}
