"use client"

import { Badge } from "@workspace/ui/components/badge"
import { getStatusBgColor, getStatusDotColor } from "../lib/formatters"

interface StatusBadgeProps {
  status: string
  showDot?: boolean
}

export function StatusBadge({ status, showDot = true }: StatusBadgeProps) {
  if (!status) return null

  return (
    <Badge variant="outline" className={`text-xs px-1.5 py-0 ${getStatusBgColor(status)}`}>
      {showDot && (
        <span
          className={`inline-block w-1.5 h-1.5 rounded-full mr-1 ${getStatusDotColor(status)}`}
        />
      )}
      {status}
    </Badge>
  )
}
