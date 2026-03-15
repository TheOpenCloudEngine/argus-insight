import {
  Activity,
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  CheckCircle2,
  Clock,
  Cpu,
  HardDrive,
  Server,
  Wifi,
} from "lucide-react"

import { Badge } from "@workspace/ui/components/badge"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@workspace/ui/components/card"
import { Separator } from "@workspace/ui/components/separator"
import { DashboardHeader } from "@/components/dashboard-header"

const stats = [
  {
    title: "전체 서버",
    value: "24",
    change: "+2",
    trend: "up",
    description: "지난 달 대비",
    icon: Server,
    color: "text-blue-500",
    bg: "bg-blue-500/10",
  },
  {
    title: "CPU 사용률",
    value: "68%",
    change: "-3%",
    trend: "down",
    description: "평균 사용률",
    icon: Cpu,
    color: "text-amber-500",
    bg: "bg-amber-500/10",
  },
  {
    title: "네트워크 트래픽",
    value: "2.4 GB/s",
    change: "+12%",
    trend: "up",
    description: "현재 처리량",
    icon: Wifi,
    color: "text-green-500",
    bg: "bg-green-500/10",
  },
  {
    title: "디스크 사용량",
    value: "72%",
    change: "+5%",
    trend: "up",
    description: "전체 용량 대비",
    icon: HardDrive,
    color: "text-purple-500",
    bg: "bg-purple-500/10",
  },
]

const recentAlerts = [
  {
    id: 1,
    server: "web-server-01",
    message: "CPU 사용률 90% 초과",
    severity: "critical",
    time: "5분 전",
  },
  {
    id: 2,
    server: "db-server-02",
    message: "디스크 공간 부족 경고",
    severity: "warning",
    time: "12분 전",
  },
  {
    id: 3,
    server: "cache-server-01",
    message: "메모리 사용률 정상화",
    severity: "info",
    time: "28분 전",
  },
  {
    id: 4,
    server: "api-server-03",
    message: "응답 지연 감지",
    severity: "warning",
    time: "1시간 전",
  },
  {
    id: 5,
    server: "web-server-02",
    message: "서비스 재시작 완료",
    severity: "success",
    time: "2시간 전",
  },
]

const serverStatus = [
  { name: "web-server-01", status: "critical", cpu: 92, memory: 78, uptime: "3d 12h" },
  { name: "web-server-02", status: "healthy", cpu: 45, memory: 62, uptime: "15d 8h" },
  { name: "db-server-01", status: "healthy", cpu: 38, memory: 81, uptime: "30d 2h" },
  { name: "db-server-02", status: "warning", cpu: 65, memory: 88, uptime: "8d 5h" },
  { name: "api-server-01", status: "healthy", cpu: 52, memory: 55, uptime: "12d 19h" },
  { name: "api-server-03", status: "warning", cpu: 71, memory: 67, uptime: "5d 3h" },
]

const severityConfig = {
  critical: { label: "위험", className: "bg-destructive/10 text-destructive border-destructive/20" },
  warning: { label: "경고", className: "bg-amber-500/10 text-amber-600 border-amber-500/20 dark:text-amber-400" },
  info: { label: "정보", className: "bg-blue-500/10 text-blue-600 border-blue-500/20 dark:text-blue-400" },
  success: { label: "정상", className: "bg-green-500/10 text-green-600 border-green-500/20 dark:text-green-400" },
}

const statusConfig = {
  healthy: { label: "정상", icon: CheckCircle2, className: "text-green-500" },
  warning: { label: "경고", icon: AlertTriangle, className: "text-amber-500" },
  critical: { label: "위험", icon: AlertTriangle, className: "text-destructive" },
}

export default function DashboardPage() {
  return (
    <>
      <DashboardHeader
        title="대시보드"
        description="시스템 현황 및 모니터링 개요"
      />
      <div className="flex flex-1 flex-col gap-4 p-4">
        {/* 통계 카드 */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {stats.map((stat) => {
            const Icon = stat.icon
            const isUp = stat.trend === "up"
            const TrendIcon = isUp ? ArrowUpRight : ArrowDownRight
            return (
              <Card key={stat.title}>
                <CardHeader className="flex flex-row items-center justify-between pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    {stat.title}
                  </CardTitle>
                  <div className={`rounded-md p-1.5 ${stat.bg}`}>
                    <Icon className={`h-4 w-4 ${stat.color}`} />
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{stat.value}</div>
                  <div className="flex items-center gap-1 mt-1">
                    <TrendIcon
                      className={`h-3.5 w-3.5 ${isUp ? "text-green-500" : "text-red-500"}`}
                    />
                    <span
                      className={`text-xs font-medium ${isUp ? "text-green-500" : "text-red-500"}`}
                    >
                      {stat.change}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {stat.description}
                    </span>
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>

        {/* 서버 현황 + 알림 */}
        <div className="grid gap-4 lg:grid-cols-5">
          {/* 서버 상태 테이블 */}
          <Card className="lg:col-span-3">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Activity className="h-4 w-4" />
                서버 현황
              </CardTitle>
              <CardDescription>실시간 서버 상태 모니터링</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-1">
                <div className="grid grid-cols-[1fr_80px_60px_60px_80px] gap-2 px-2 py-1 text-xs font-medium text-muted-foreground">
                  <span>서버명</span>
                  <span className="text-center">상태</span>
                  <span className="text-center">CPU</span>
                  <span className="text-center">메모리</span>
                  <span className="text-right">업타임</span>
                </div>
                <Separator />
                {serverStatus.map((server) => {
                  const config = statusConfig[server.status as keyof typeof statusConfig]
                  const StatusIcon = config.icon
                  return (
                    <div
                      key={server.name}
                      className="grid grid-cols-[1fr_80px_60px_60px_80px] gap-2 items-center px-2 py-2 rounded-md hover:bg-muted/50 transition-colors"
                    >
                      <span className="text-sm font-medium truncate">{server.name}</span>
                      <div className="flex items-center justify-center gap-1">
                        <StatusIcon className={`h-3.5 w-3.5 ${config.className}`} />
                        <span className={`text-xs ${config.className}`}>{config.label}</span>
                      </div>
                      <div className="text-center">
                        <span
                          className={`text-xs font-medium ${
                            server.cpu > 80
                              ? "text-destructive"
                              : server.cpu > 60
                              ? "text-amber-500"
                              : "text-muted-foreground"
                          }`}
                        >
                          {server.cpu}%
                        </span>
                      </div>
                      <div className="text-center">
                        <span
                          className={`text-xs font-medium ${
                            server.memory > 85
                              ? "text-destructive"
                              : server.memory > 70
                              ? "text-amber-500"
                              : "text-muted-foreground"
                          }`}
                        >
                          {server.memory}%
                        </span>
                      </div>
                      <div className="text-right">
                        <span className="text-xs text-muted-foreground flex items-center justify-end gap-1">
                          <Clock className="h-3 w-3" />
                          {server.uptime}
                        </span>
                      </div>
                    </div>
                  )
                })}
              </div>
            </CardContent>
          </Card>

          {/* 최근 알림 */}
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4" />
                최근 알림
              </CardTitle>
              <CardDescription>최근 발생한 시스템 이벤트</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {recentAlerts.map((alert) => {
                  const config = severityConfig[alert.severity as keyof typeof severityConfig]
                  return (
                    <div key={alert.id} className="flex flex-col gap-1.5">
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex flex-col gap-1 min-w-0">
                          <span className="text-xs font-medium text-muted-foreground truncate">
                            {alert.server}
                          </span>
                          <span className="text-sm leading-tight">{alert.message}</span>
                        </div>
                        <Badge
                          variant="outline"
                          className={`shrink-0 text-[10px] px-1.5 py-0.5 ${config.className}`}
                        >
                          {config.label}
                        </Badge>
                      </div>
                      <span className="text-[11px] text-muted-foreground flex items-center gap-1">
                        <Clock className="h-2.5 w-2.5" />
                        {alert.time}
                      </span>
                      <Separator />
                    </div>
                  )
                })}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  )
}
