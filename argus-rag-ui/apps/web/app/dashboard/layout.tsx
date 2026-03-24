"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Database,
  LayoutDashboard,
  Link2,
  Search,
  Settings,
  Clock,
  PanelLeft,
  ChevronLeft,
} from "lucide-react";
import { useState } from "react";

const NAV_GROUPS = [
  {
    label: "RAG Management",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
      { href: "/dashboard/collections", label: "Collections", icon: Database },
      { href: "/dashboard/search", label: "Search Playground", icon: Search },
    ],
  },
  {
    label: "Data Sources",
    items: [
      { href: "/dashboard/sources", label: "Data Sources", icon: Link2 },
      { href: "/dashboard/jobs", label: "Job History", icon: Clock },
    ],
  },
  {
    label: "Administration",
    items: [
      { href: "/dashboard/settings", label: "Settings", icon: Settings },
    ],
  },
];

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className="flex h-screen">
      {/* Sidebar — dark blue-gray matching catalog-ui */}
      <aside
        className="flex flex-col border-r transition-all duration-200"
        style={{
          width: collapsed ? 56 : 240,
          background: "oklch(0.30 0.02 260)",
          color: "oklch(0.93 0.01 260)",
          borderColor: "oklch(1 0 0 / 12%)",
        }}
      >
        {/* Header */}
        <div
          className="flex items-center gap-2 px-3 border-b"
          style={{
            height: 48,
            borderColor: "oklch(1 0 0 / 12%)",
          }}
        >
          <div
            className="flex items-center justify-center rounded-md font-bold text-xs"
            style={{
              width: 28,
              height: 28,
              background: "oklch(0.623 0.214 259.815)",
              color: "oklch(0.97 0.014 254.604)",
            }}
          >
            AR
          </div>
          {!collapsed && (
            <span className="text-sm font-semibold tracking-tight">Argus RAG</span>
          )}
        </div>

        {/* Navigation groups */}
        <nav className="flex-1 overflow-y-auto py-2 px-2 space-y-4">
          {NAV_GROUPS.map((group) => (
            <div key={group.label}>
              {!collapsed && (
                <div
                  className="text-[10px] font-semibold uppercase tracking-wider px-2 mb-1"
                  style={{ color: "oklch(0.65 0.01 260)" }}
                >
                  {group.label}
                </div>
              )}
              <div className="space-y-0.5">
                {group.items.map((item) => {
                  const isActive =
                    pathname === item.href ||
                    (item.href !== "/dashboard" &&
                      pathname.startsWith(item.href));
                  const Icon = item.icon;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      title={item.label}
                      className="flex items-center gap-2.5 rounded-md text-sm transition-colors"
                      style={{
                        padding: collapsed ? "7px 10px" : "7px 10px",
                        background: isActive
                          ? "oklch(0.36 0.03 260)"
                          : "transparent",
                        color: isActive
                          ? "oklch(0.95 0.01 260)"
                          : "oklch(0.80 0.01 260)",
                      }}
                    >
                      <Icon className="h-4 w-4 shrink-0" />
                      {!collapsed && item.label}
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        {/* Footer */}
        <div
          className="px-3 py-2 border-t text-[10px] flex items-center justify-between"
          style={{
            color: "oklch(0.55 0.01 260)",
            borderColor: "oklch(1 0 0 / 12%)",
          }}
        >
          {!collapsed && <span>argus-rag-server :4800</span>}
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="p-1 rounded hover:opacity-80"
            title={collapsed ? "Expand" : "Collapse"}
          >
            {collapsed ? (
              <PanelLeft className="h-3.5 w-3.5" />
            ) : (
              <ChevronLeft className="h-3.5 w-3.5" />
            )}
          </button>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header bar — matching catalog h-16 style */}
        <header className="flex h-14 shrink-0 items-center gap-3 border-b px-4">
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="p-1.5 rounded-md hover:bg-[var(--accent)] text-[var(--muted-foreground)]"
          >
            <PanelLeft className="h-4 w-4" />
          </button>
          <div className="h-4 w-px bg-[var(--border)]" />
          <h1 className="text-base font-semibold text-[var(--foreground)]">
            {getPageTitle(pathname)}
          </h1>
        </header>

        {/* Content */}
        <main className="flex-1 overflow-auto">
          <div className="p-6">{children}</div>
        </main>
      </div>
    </div>
  );
}

function getPageTitle(pathname: string): string {
  if (pathname === "/dashboard") return "Dashboard";
  if (pathname.startsWith("/dashboard/collections/")) return "Collection Detail";
  if (pathname.startsWith("/dashboard/collections")) return "Collections";
  if (pathname.startsWith("/dashboard/search")) return "Search Playground";
  if (pathname.startsWith("/dashboard/sources")) return "Data Sources";
  if (pathname.startsWith("/dashboard/jobs")) return "Job History";
  if (pathname.startsWith("/dashboard/settings")) return "Settings";
  return "Argus RAG";
}
