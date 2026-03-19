import {
  BarChart3,
  Bell,
  BookOpen,
  FolderOpen,
  HelpCircle,
  LayoutDashboard,
  Library,
  Monitor,
  Server,
  ServerCog,
  Settings,
  Shield,
  SlidersHorizontal,
  Terminal,
  Users,
  Zap,
} from "lucide-react"
import type { LucideIcon } from "lucide-react"

const iconMap: Record<string, LucideIcon> = {
  BarChart3,
  Bell,
  BookOpen,
  FolderOpen,
  LayoutDashboard,
  Library,
  Monitor,
  Server,
  ServerCog,
  Settings,
  Shield,
  SlidersHorizontal,
  Terminal,
  Users,
  Zap,
}

export function getIcon(name: string): LucideIcon {
  return iconMap[name] ?? HelpCircle
}
