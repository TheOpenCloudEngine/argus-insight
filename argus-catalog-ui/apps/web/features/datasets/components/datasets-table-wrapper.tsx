"use client"

import { useDatasets } from "./datasets-provider"
import { DatasetsTable } from "./datasets-table"

export function DatasetsTableWrapper() {
  const { datasets, isLoading } = useDatasets()
  return <DatasetsTable data={datasets} isLoading={isLoading} />
}
