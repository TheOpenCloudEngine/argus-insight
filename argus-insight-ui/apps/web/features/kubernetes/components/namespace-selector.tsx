"use client"

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"
import { useNamespaces } from "../hooks/use-k8s-resources"

interface NamespaceSelectorProps {
  value: string
  onChange: (ns: string) => void
}

export function NamespaceSelector({ value, onChange }: NamespaceSelectorProps) {
  const { namespaces, loading } = useNamespaces()

  return (
    <Select value={value} onValueChange={onChange} disabled={loading}>
      <SelectTrigger className="w-[200px] h-8 text-sm">
        <SelectValue placeholder="All namespaces" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="_all">All namespaces</SelectItem>
        {namespaces.map((ns) => (
          <SelectItem key={ns} value={ns}>
            {ns}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
