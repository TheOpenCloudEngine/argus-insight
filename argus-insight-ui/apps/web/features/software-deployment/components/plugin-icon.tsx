"use client"

import { useState } from "react"
import Image from "next/image"
import {
  Blocks,
  Box,
  Brain,
  Code,
  Database,
  GitBranch,
  HelpCircle,
  Sparkles,
  Star,
  Workflow,
} from "lucide-react"
import type { LucideIcon } from "lucide-react"

/** Lucide fallback icons keyed by plugin.yaml icon value */
const lucideFallback: Record<string, LucideIcon> = {
  gitlab: GitBranch,
  airflow: Blocks,
  mlflow: Box,
  minio: Database,
  jupyter: Code,
  neo4j: Database,
  milvus: Database,
  brain: Brain,
  mindsdb: Brain,
  kserve: Box,
  code: Code,
  database: Database,
  trino: Database,
  starrocks: Star,
  greenplum: Database,
  hadoop: Blocks,
  spark: Sparkles,
  kafka: Workflow,
  nifi: Workflow,
  mysql: Database,
  mariadb: Database,
  postgresql: Database,
  mssql: Database,
  oracle: Database,
  impala: Database,
  kudu: Database,
  zookeeper: Blocks,
  feast: Database,
}

interface PluginIconProps {
  icon: string
  size?: number
  className?: string
}

export function PluginIcon({ icon, size = 32, className }: PluginIconProps) {
  const [imgError, setImgError] = useState(false)

  if (!imgError) {
    return (
      <Image
        src={`/icons/plugins/${icon}.svg`}
        alt={icon}
        width={size}
        height={size}
        className={className}
        onError={() => setImgError(true)}
      />
    )
  }

  const FallbackIcon = lucideFallback[icon] ?? HelpCircle
  return <FallbackIcon size={size} className={className} />
}
