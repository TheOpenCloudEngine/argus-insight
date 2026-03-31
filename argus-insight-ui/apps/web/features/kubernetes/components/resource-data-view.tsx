"use client"

import { useMemo, useState } from "react"
import { Eye, EyeOff } from "lucide-react"
import dynamic from "next/dynamic"
import { Button } from "@workspace/ui/components/button"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@workspace/ui/components/card"
import type { K8sResourceItem } from "../types"

const MonacoEditor = dynamic(() => import("@monaco-editor/react"), { ssr: false })

interface ResourceDataViewProps {
  resource: K8sResourceItem
}

/**
 * Display ConfigMap data or Secret data in a readable format.
 * Secrets are base64-encoded and hidden by default.
 */
export function ResourceDataView({ resource }: ResourceDataViewProps) {
  const isSecret = resource.kind === "Secret"
  const data = resource.data as Record<string, string> | undefined
  const [revealed, setRevealed] = useState<Set<string>>(new Set())

  if (!data || Object.keys(data).length === 0) {
    return <p className="text-sm text-muted-foreground p-4 text-center">No data entries</p>
  }

  const toggleReveal = (key: string) => {
    setRevealed((prev) => {
      const next = new Set(prev)
      if (next.has(key)) {
        next.delete(key)
      } else {
        next.add(key)
      }
      return next
    })
  }

  const decodeBase64 = (value: string): string => {
    try {
      return atob(value)
    } catch {
      return value
    }
  }

  return (
    <div className="space-y-3">
      {Object.entries(data).map(([key, value]) => {
        const isRevealed = revealed.has(key)
        const displayValue = isSecret
          ? isRevealed
            ? decodeBase64(value)
            : "••••••••"
          : value

        return (
          <Card key={key}>
            <CardHeader className="py-2 flex flex-row items-center justify-between">
              <CardTitle className="text-sm font-mono">{key}</CardTitle>
              {isSecret && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6"
                  onClick={() => toggleReveal(key)}
                >
                  {isRevealed ? (
                    <EyeOff className="h-3.5 w-3.5" />
                  ) : (
                    <Eye className="h-3.5 w-3.5" />
                  )}
                </Button>
              )}
            </CardHeader>
            <CardContent>
              <DataMonacoViewer value={displayValue} />
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}

function DataMonacoViewer({ value }: { value: string }) {
  const lineCount = useMemo(() => Math.max(value.split("\n").length, 3), [value])
  const height = Math.min(lineCount * 22 + 16, 400)

  return (
    <div className="rounded-md border overflow-hidden">
      <MonacoEditor
        height={`${height}px`}
        language="plaintext"
        theme="light"
        value={value}
        options={{
          readOnly: true,
          minimap: { enabled: false },
          fontSize: 14,
          fontFamily: "var(--font-d2coding), 'D2Coding', monospace",
          lineNumbers: "on",
          scrollBeyondLastLine: false,
          wordWrap: "on",
          tabSize: 2,
          automaticLayout: true,
          renderLineHighlight: "none",
          padding: { top: 8, bottom: 8 },
        }}
      />
    </div>
  )
}
