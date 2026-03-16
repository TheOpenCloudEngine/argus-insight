"use client"

import { DashboardHeader } from "@/components/dashboard-header"
import { UsersDialogs } from "@/features/users/components/users-dialogs"
import { UsersPrimaryButtons } from "@/features/users/components/users-primary-buttons"
import { UsersProvider } from "@/features/users/components/users-provider"
import { UsersTableWrapper } from "@/features/users/components/users-table-wrapper"

export default function UsersPage() {
  return (
    <UsersProvider>
      <DashboardHeader
        title="사용자 관리"
        description="사용자 목록 및 권한을 관리합니다."
      />
      <div className="flex flex-1 flex-col gap-4 p-4">
        <div className="flex flex-wrap items-end justify-end gap-2">
          <UsersPrimaryButtons />
        </div>
        <UsersTableWrapper />
      </div>

      <UsersDialogs />
    </UsersProvider>
  )
}
