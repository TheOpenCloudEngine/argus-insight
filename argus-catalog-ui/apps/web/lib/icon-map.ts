import {
  BookOpen,
  Database,
  HelpCircle,
  LayoutDashboard,
  Server,
  Tags,
} from "lucide-react"
import type { LucideIcon } from "lucide-react"

const iconMap: Record<string, LucideIcon> = {
  BookOpen,
  Database,
  LayoutDashboard,
  Server,
  Tags,
}

export function getIcon(name: string): LucideIcon {
  return iconMap[name] ?? HelpCircle
}
