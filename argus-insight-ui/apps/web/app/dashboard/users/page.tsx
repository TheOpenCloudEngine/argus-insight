import { DashboardHeader } from "@/components/dashboard-header"
import { UsersDialogs } from "@/features/users/components/users-dialogs"
import { UsersPrimaryButtons } from "@/features/users/components/users-primary-buttons"
import { UsersProvider } from "@/features/users/components/users-provider"
import { UsersTable } from "@/features/users/components/users-table"
import { users } from "@/features/users/data/users"

export default function UsersPage() {
  return (
    <UsersProvider>
      <DashboardHeader
        title="사용자 관리"
        description="사용자 목록 및 권한을 관리합니다."
      />
      <div className="flex flex-1 flex-col gap-4 p-4">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <div>
            <h2 className="text-2xl font-bold tracking-tight">User List</h2>
            <p className="text-muted-foreground">
              Manage your users and their roles here.
            </p>
          </div>
          <UsersPrimaryButtons />
        </div>
        <UsersTable data={users} />
      </div>

      <UsersDialogs />
    </UsersProvider>
  )
}
