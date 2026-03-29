import {
  BarChart3,
  Bell,
  Blocks,
  BookOpen,
  Code,
  Container,
  FolderOpen,
  Globe,
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
  Blocks,
  BookOpen,
  Code,
  Container,
  FolderOpen,
  Globe,
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
