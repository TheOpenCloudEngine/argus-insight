import {
  BookOpen,
  Box,
  Database,
  FolderOpen,
  HelpCircle,
  LayoutDashboard,
  Server,
  Settings,
  Tags,
  Users,
} from "lucide-react"
import type { LucideIcon } from "lucide-react"

const iconMap: Record<string, LucideIcon> = {
  BookOpen,
  Box,
  Database,
  FolderOpen,
  LayoutDashboard,
  Server,
  Settings,
  Tags,
  Users,
}

export function getIcon(name: string): LucideIcon {
  return iconMap[name] ?? HelpCircle
}
