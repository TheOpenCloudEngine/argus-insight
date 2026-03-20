"use client"

import React, { useCallback, useEffect, useRef, useState } from "react"

import useDialogState from "@/hooks/use-dialog-state"
import { fetchDatasets, type PaginatedDatasets } from "../api"
import { type DatasetSummary } from "../data/schema"

type DatasetsDialogType = "add" | "edit" | "delete"

type SearchParams = {
  search: string
  platform: string
  origin: string
  status: string
  tag: string
}

type DatasetsContextType = {
  open: DatasetsDialogType | null
  setOpen: (str: DatasetsDialogType | null) => void
  currentRow: DatasetSummary | null
  setCurrentRow: React.Dispatch<React.SetStateAction<DatasetSummary | null>>
  datasets: DatasetSummary[]
  total: number
  page: number
  pageSize: number
  isLoading: boolean
  setPage: (page: number) => void
  setPageSize: (size: number) => void
  searchDatasets: (params: SearchParams) => void
  refreshDatasets: () => Promise<void>
}

const DatasetsContext = React.createContext<DatasetsContextType | null>(null)

export function DatasetsProvider({
  children,
}: {
  children: React.ReactNode
}) {
  const [open, setOpen] = useDialogState<DatasetsDialogType>(null)
  const [currentRow, setCurrentRow] = useState<DatasetSummary | null>(null)
  const [datasets, setDatasets] = useState<DatasetSummary[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [isLoading, setIsLoading] = useState(true)

  const appliedFiltersRef = useRef<SearchParams>({
    search: "",
    platform: "",
    origin: "",
    status: "",
    tag: "",
  })

  const loadDatasets = useCallback(
    async (params: {
      page: number
      pageSize: number
      search: string
      platform: string
      origin: string
      status: string
      tag: string
    }) => {
      try {
        setIsLoading(true)
        const data: PaginatedDatasets = await fetchDatasets({
          page: params.page,
          pageSize: params.pageSize,
          search: params.search || undefined,
          platform: params.platform || undefined,
          origin: params.origin || undefined,
          status: params.status || undefined,
          tag: params.tag || undefined,
        })
        setDatasets(data.items)
        setTotal(data.total)
      } catch (err) {
        console.error("Failed to fetch datasets:", err)
      } finally {
        setIsLoading(false)
      }
    },
    []
  )

  useEffect(() => {
    loadDatasets({
      page: 1,
      pageSize,
      search: "",
      platform: "",
      origin: "",
      status: "",
      tag: "",
    })
  }, [loadDatasets, pageSize])

  const handleSetPage = useCallback(
    (newPage: number) => {
      setPage(newPage)
      const f = appliedFiltersRef.current
      loadDatasets({ page: newPage, pageSize, ...f })
    },
    [loadDatasets, pageSize]
  )

  const handleSetPageSize = useCallback(
    (size: number) => {
      setPageSize(size)
      setPage(1)
      const f = appliedFiltersRef.current
      loadDatasets({ page: 1, pageSize: size, ...f })
    },
    [loadDatasets]
  )

  const searchDatasets = useCallback(
    (params: SearchParams) => {
      appliedFiltersRef.current = params
      setPage(1)
      loadDatasets({ page: 1, pageSize, ...params })
    },
    [loadDatasets, pageSize]
  )

  const refreshDatasets = useCallback(async () => {
    const f = appliedFiltersRef.current
    await loadDatasets({ page, pageSize, ...f })
  }, [loadDatasets, page, pageSize])

  return (
    <DatasetsContext
      value={{
        open,
        setOpen,
        currentRow,
        setCurrentRow,
        datasets,
        total,
        page,
        pageSize,
        isLoading,
        setPage: handleSetPage,
        setPageSize: handleSetPageSize,
        searchDatasets,
        refreshDatasets,
      }}
    >
      {children}
    </DatasetsContext>
  )
}

export const useDatasets = () => {
  const ctx = React.useContext(DatasetsContext)
  if (!ctx) {
    throw new Error("useDatasets must be used within <DatasetsProvider>")
  }
  return ctx
}
