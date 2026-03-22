import {
  BookOpen,
  Box,
  Database,
  FolderOpen,
  Globe,
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
  Globe,
  LayoutDashboard,
  Server,
  Settings,
  Tags,
  Users,
}

export function getIcon(name: string): LucideIcon {
  return iconMap[name] ?? HelpCircle
}
