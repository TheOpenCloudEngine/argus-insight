"use client"

import { useState } from "react"
import { Eye, EyeOff } from "lucide-react"
import { Button } from "@workspace/ui/components/button"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@workspace/ui/components/card"
import type { K8sResourceItem } from "../types"

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
              <pre className="text-xs bg-muted p-2 rounded-md overflow-auto max-h-[200px] font-mono whitespace-pre-wrap break-all">
                {displayValue}
              </pre>
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}
