import { SidebarInset, SidebarProvider } from "@workspace/ui/components/sidebar"
import { TooltipProvider } from "@workspace/ui/components/tooltip"
import { AppSidebar } from "@/components/app-sidebar"
import { AuthGuardWrapper } from "@/components/auth-guard-wrapper" // Added for SSO AUTH

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    // Added for SSO AUTH - redirects unauthenticated users to /login
    <AuthGuardWrapper>
      <TooltipProvider>
        <SidebarProvider>
          <AppSidebar />
          <SidebarInset>
            {children}
          </SidebarInset>
        </SidebarProvider>
      </TooltipProvider>
    </AuthGuardWrapper>
  )
}
