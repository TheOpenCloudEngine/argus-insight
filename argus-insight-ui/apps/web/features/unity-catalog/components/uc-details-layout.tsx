"use client"

type UCDetailsLayoutProps = {
  children: React.ReactNode
  sidebar?: React.ReactNode
}

export function UCDetailsLayout({ children, sidebar }: UCDetailsLayoutProps) {
  return (
    <div className="flex gap-6">
      <div className="min-w-0 flex-1 space-y-6">
        {children}
      </div>
      {sidebar && (
        <aside className="hidden w-64 shrink-0 lg:block">
          <div className="sticky top-4 space-y-6">
            {sidebar}
          </div>
        </aside>
      )}
    </div>
  )
}
