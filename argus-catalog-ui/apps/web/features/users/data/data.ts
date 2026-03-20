import { UserCheck, Users } from "lucide-react"

import { type UserStatus } from "./schema"

/**
 * Visual style mapping for user status badges.
 *
 * Maps each UserStatus value to a Tailwind CSS class string used by the
 * Badge component in the users table. The classes control background color,
 * text color, and border color to provide at-a-glance status indication:
 *
 * - active   → Primary color (blue/brand) indicating a healthy, usable account.
 * - inactive → Destructive color (red) indicating a deactivated account.
 */
export const callTypes = new Map<UserStatus, string>([
  [
    "active",
    "bg-primary/10 text-primary border-primary/30",
  ],
  [
    "inactive",
    "bg-destructive/10 dark:bg-destructive/50 text-destructive dark:text-primary border-destructive/10",
  ],
])

/**
 * Role definitions for filter options and display.
 *
 * Each entry contains:
 * - label: Human-readable name shown in the UI (e.g. filter dropdown, table cell).
 * - value: Machine value matching the backend role name (lowercase).
 * - icon:  Lucide icon component rendered next to the role label.
 *
 * Used by the DataTableToolbar's faceted filter and the role column renderer.
 */
export const roles = [
  {
    label: "Admin",
    value: "admin",
    icon: UserCheck,
  },
  {
    label: "User",
    value: "user",
    icon: Users,
  },
] as const
