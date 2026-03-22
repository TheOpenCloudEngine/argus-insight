import { Shield, UserCheck, Users } from "lucide-react"

import { type UserStatus } from "./schema"

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

export const roles = [
  {
    label: "Admin",
    value: "argus-admin",
    icon: UserCheck,
  },
  {
    label: "Superuser",
    value: "argus-superuser",
    icon: Shield,
  },
  {
    label: "User",
    value: "argus-user",
    icon: Users,
  },
] as const
