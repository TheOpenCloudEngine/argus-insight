import {
  BarChart3,
  Bell,
  HelpCircle,
  LayoutDashboard,
  Monitor,
  Server,
  Settings,
  Shield,
  SlidersHorizontal,
  Users,
  Zap,
} from "lucide-react"
import type { LucideIcon } from "lucide-react"

const iconMap: Record<string, LucideIcon> = {
  BarChart3,
  Bell,
  LayoutDashboard,
  Monitor,
  Server,
  Settings,
  Shield,
  SlidersHorizontal,
  Users,
  Zap,
}

export function getIcon(name: string): LucideIcon {
  return iconMap[name] ?? HelpCircle
}
