"use client"

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react"
import type { Notebook, Section, PageListItem, Page } from "../api"
import {
  fetchNotebooks,
  fetchSections,
  fetchPages,
  fetchPage,
  createNotebook as apiCreateNotebook,
  deleteNotebook as apiDeleteNotebook,
  updateNotebook as apiUpdateNotebook,
  createSection as apiCreateSection,
  deleteSection as apiDeleteSection,
  createPage as apiCreatePage,
  deletePage as apiDeletePage,
  updatePage as apiUpdatePage,
} from "../api"

type NotesContextType = {
  // Data
  notebooks: Notebook[]
  sections: Section[]
  pages: PageListItem[]
  currentNotebook: Notebook | null
  currentSection: Section | null
  currentPage: Page | null
  loading: boolean

  // Actions
  loadNotebooks: (search?: string) => Promise<void>
  selectNotebook: (notebook: Notebook) => Promise<void>
  selectSection: (section: Section) => Promise<void>
  selectPage: (pageId: number) => Promise<void>
  createNotebook: (title: string, description?: string, color?: string) => Promise<Notebook>
  changeNotebookColor: (id: number, color: string) => Promise<void>
  removeNotebook: (id: number) => Promise<void>
  addSection: (title: string) => Promise<Section | null>
  removeSection: (id: number) => Promise<void>
  addPage: (title: string) => Promise<Page | null>
  removePage: (id: number) => Promise<void>
  savePage: (pageId: number, title: string, content: string, changeSummary?: string) => Promise<Page>
  refreshCurrentPage: () => Promise<void>
}

const NotesContext = createContext<NotesContextType | null>(null)

export function useNotes() {
  const ctx = useContext(NotesContext)
  if (!ctx) throw new Error("useNotes must be used within NotesProvider")
  return ctx
}

export function NotesProvider({ children }: { children: ReactNode }) {
  const [notebooks, setNotebooks] = useState<Notebook[]>([])
  const [sections, setSections] = useState<Section[]>([])
  const [pages, setPages] = useState<PageListItem[]>([])
  const [currentNotebook, setCurrentNotebook] = useState<Notebook | null>(null)
  const [currentSection, setCurrentSection] = useState<Section | null>(null)
  const [currentPage, setCurrentPage] = useState<Page | null>(null)
  const [loading, setLoading] = useState(false)

  const loadNotebooks = useCallback(async (search?: string) => {
    setLoading(true)
    try {
      const data = await fetchNotebooks(search)
      setNotebooks(data.items)
    } finally {
      setLoading(false)
    }
  }, [])

  const selectNotebook = useCallback(async (notebook: Notebook) => {
    setCurrentNotebook(notebook)
    setCurrentSection(null)
    setCurrentPage(null)
    setPages([])
    const secs = await fetchSections(notebook.id)
    setSections(secs)
    if (secs.length > 0 && secs[0]) {
      setCurrentSection(secs[0])
      const ps = await fetchPages(secs[0].id)
      setPages(ps)
    }
  }, [])

  const selectSection = useCallback(async (section: Section) => {
    setCurrentSection(section)
    setCurrentPage(null)
    const ps = await fetchPages(section.id)
    setPages(ps)
  }, [])

  const selectPage = useCallback(async (pageId: number) => {
    const page = await fetchPage(pageId)
    setCurrentPage(page)
  }, [])

  const createNotebook = useCallback(
    async (title: string, description?: string, color?: string) => {
      const nb = await apiCreateNotebook({ title, description, color })
      await loadNotebooks()
      return nb
    },
    [loadNotebooks],
  )

  const changeNotebookColor = useCallback(
    async (id: number, color: string) => {
      await apiUpdateNotebook(id, { color })
      setNotebooks((prev) =>
        prev.map((nb) => (nb.id === id ? { ...nb, color } : nb)),
      )
    },
    [],
  )

  const removeNotebook = useCallback(
    async (id: number) => {
      await apiDeleteNotebook(id)
      if (currentNotebook?.id === id) {
        setCurrentNotebook(null)
        setSections([])
        setPages([])
        setCurrentSection(null)
        setCurrentPage(null)
      }
      await loadNotebooks()
    },
    [currentNotebook, loadNotebooks],
  )

  const addSection = useCallback(
    async (title: string) => {
      if (!currentNotebook) return null
      const sec = await apiCreateSection(currentNotebook.id, { title })
      const secs = await fetchSections(currentNotebook.id)
      setSections(secs)
      return sec
    },
    [currentNotebook],
  )

  const removeSection = useCallback(
    async (id: number) => {
      await apiDeleteSection(id)
      if (!currentNotebook) return
      const secs = await fetchSections(currentNotebook.id)
      setSections(secs)
      if (currentSection?.id === id) {
        setCurrentSection(secs[0] ?? null)
        if (secs[0]) {
          const ps = await fetchPages(secs[0].id)
          setPages(ps)
        } else {
          setPages([])
        }
        setCurrentPage(null)
      }
    },
    [currentNotebook, currentSection],
  )

  const addPage = useCallback(
    async (title: string) => {
      if (!currentSection) return null
      const page = await apiCreatePage(currentSection.id, { title })
      const ps = await fetchPages(currentSection.id)
      setPages(ps)
      setCurrentPage(page)
      return page
    },
    [currentSection],
  )

  const removePage = useCallback(
    async (id: number) => {
      await apiDeletePage(id)
      if (!currentSection) return
      const ps = await fetchPages(currentSection.id)
      setPages(ps)
      if (currentPage?.id === id) {
        setCurrentPage(null)
      }
    },
    [currentSection, currentPage],
  )

  const savePage = useCallback(
    async (pageId: number, title: string, content: string, changeSummary?: string) => {
      const page = await apiUpdatePage(pageId, { title, content, change_summary: changeSummary })
      setCurrentPage(page)
      if (currentSection) {
        const ps = await fetchPages(currentSection.id)
        setPages(ps)
      }
      return page
    },
    [currentSection],
  )

  const refreshCurrentPage = useCallback(async () => {
    if (currentPage) {
      const page = await fetchPage(currentPage.id)
      setCurrentPage(page)
    }
  }, [currentPage])

  useEffect(() => {
    loadNotebooks()
  }, [loadNotebooks])

  return (
    <NotesContext.Provider
      value={{
        notebooks,
        sections,
        pages,
        currentNotebook,
        currentSection,
        currentPage,
        loading,
        loadNotebooks,
        selectNotebook,
        selectSection,
        selectPage,
        createNotebook,
        changeNotebookColor,
        removeNotebook,
        addSection,
        removeSection,
        addPage,
        removePage,
        savePage,
        refreshCurrentPage,
      }}
    >
      {children}
    </NotesContext.Provider>
  )
}
