"use client"

import { useCallback, useState } from "react"
import { TerminalIcon } from "lucide-react"
import { Button } from "@workspace/ui/components/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@workspace/ui/components/card"
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"
import { TerminalView } from "./terminal-view"

function buildWsUrl(agentId: string): string {
  // Use NEXT_PUBLIC_API_URL if set, otherwise derive from window.location
  const base =
    process.env.NEXT_PUBLIC_API_URL ??
    `${window.location.protocol}//${window.location.hostname}:8080`
  const wsBase = base.replace(/^http/, "ws")
  return `${wsBase}/api/v1/proxy/${agentId}/terminal/ws`
}

export function TerminalPanel() {
  const [agentId, setAgentId] = useState("")
  const [activeAgent, setActiveAgent] = useState<string | null>(null)
  const [connected, setConnected] = useState(false)

  const handleConnect = useCallback(() => {
    const id = agentId.trim()
    if (!id) return
    // Force remount by clearing first
    setActiveAgent(null)
    setTimeout(() => setActiveAgent(id), 0)
  }, [agentId])

  const handleDisconnect = useCallback(() => {
    setActiveAgent(null)
    setConnected(false)
  }, [])

  return (
    <div className="flex flex-col h-full gap-4">
      {/* Connection bar */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <TerminalIcon className="h-4 w-4" />
            원격 터미널
          </CardTitle>
          <CardDescription>
            에이전트 서버에 원격 터미널로 접속합니다.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-end gap-3">
            <div className="flex-1">
              <Label htmlFor="agent-id" className="text-xs mb-1.5 block">
                에이전트 ID
              </Label>
              <Input
                id="agent-id"
                placeholder="에이전트 ID를 입력하세요"
                value={agentId}
                onChange={(e) => setAgentId(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleConnect()
                }}
                className="h-9 text-sm font-mono"
              />
            </div>
            {!activeAgent ? (
              <Button
                onClick={handleConnect}
                disabled={!agentId.trim()}
                size="sm"
                className="h-9"
              >
                접속
              </Button>
            ) : (
              <Button
                onClick={handleDisconnect}
                variant="destructive"
                size="sm"
                className="h-9"
              >
                연결 해제
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Terminal area */}
      {activeAgent ? (
        <div className="flex-1 min-h-0">
          <TerminalView
            wsUrl={buildWsUrl(activeAgent)}
            onConnectionChange={setConnected}
          />
        </div>
      ) : (
        <Card className="flex-1 flex items-center justify-center">
          <div className="text-center text-muted-foreground">
            <TerminalIcon className="h-12 w-12 mx-auto mb-3 opacity-30" />
            <p className="text-sm">에이전트에 접속하면 터미널이 표시됩니다.</p>
          </div>
        </Card>
      )}
    </div>
  )
}
