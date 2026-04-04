"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import rehypeHighlight from "rehype-highlight"
import "highlight.js/styles/github-dark.css"
import {
  Bot,
  Copy,
  Download,
  Loader2,
  Send,
  Settings2,
  Sparkles,
  StopCircle,
  Trash2,
  User,
} from "lucide-react"
import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import { Card, CardContent } from "@workspace/ui/components/card"
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"
import { Textarea } from "@workspace/ui/components/textarea"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@workspace/ui/components/tooltip"

import { authFetch } from "@/features/auth/auth-fetch"

// ── Types ─────────────────────────────────────────────────

interface ChatMessage {
  role: "system" | "user" | "assistant"
  content: string
}

interface LLMModel {
  service_id: number
  service_type: string
  service_label: string
  model: string
}

// ── Main Component ────────────────────────────────────────

export function PlaygroundChat() {
  // Chat state
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState("")
  const [streaming, setStreaming] = useState(false)
  const [streamText, setStreamText] = useState("")
  const abortRef = useRef<AbortController | null>(null)
  const chatEndRef = useRef<HTMLDivElement>(null)

  // Service state
  const [workspaceId, setWorkspaceId] = useState<number | null>(null)
  const [llmModels, setLlmModels] = useState<LLMModel[]>([])
  const [selectedModel, setSelectedModel] = useState("custom")
  const [customEndpoint, setCustomEndpoint] = useState("")
  const [customApiKey, setCustomApiKey] = useState("")
  const [customModel, setCustomModel] = useState("")

  // Parameters
  const [systemPrompt, setSystemPrompt] = useState("You are a helpful assistant.")
  const [temperature, setTemperature] = useState(0.7)
  const [topP, setTopP] = useState(0.9)
  const [maxTokens, setMaxTokens] = useState(2048)
  const [showSettings, setShowSettings] = useState(false)

  // Stats
  const [lastLatency, setLastLatency] = useState<number | null>(null)
  const [lastTokens, setLastTokens] = useState<number | null>(null)

  // Load workspace LLM models via server proxy
  useEffect(() => {
    async function loadModels() {
      // Try sessionStorage first (set by workspace page), then /workspaces/my
      let wsId: number | null = null
      const stored = sessionStorage.getItem("argus_last_workspace_id")
      if (stored) {
        wsId = Number(stored)
      } else {
        try {
          const res = await authFetch("/api/v1/workspace/workspaces/my")
          if (res.ok) {
            const workspaces: { id: number }[] = await res.json()
            if (workspaces.length > 0) wsId = workspaces[0]!.id
          }
        } catch { /* ignore */ }
      }
      if (!wsId) return
      setWorkspaceId(wsId)

      try {
        const res = await authFetch(`/api/v1/workspace/workspaces/${wsId}/llm/models`)
        if (!res.ok) return
        const data = await res.json()
        const models: LLMModel[] = data.models ?? []
        setLlmModels(models)
        if (models.length > 0 && models[0]) {
          setSelectedModel(`${models[0].service_id}:${models[0].model}`)
        }
      } catch { /* ignore */ }
    }
    loadModels()
  }, [])

  // Auto-scroll
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, streamText])

  // Send message
  const handleSend = useCallback(async () => {
    const text = input.trim()
    if (!text || streaming) return

    const userMsg: ChatMessage = { role: "user", content: text }
    const allMessages: ChatMessage[] = [
      ...(systemPrompt ? [{ role: "system" as const, content: systemPrompt }] : []),
      ...messages,
      userMsg,
    ]

    setMessages((prev) => [...prev, userMsg])
    setInput("")
    setStreaming(true)
    setStreamText("")
    setLastLatency(null)
    setLastTokens(null)

    const startTime = Date.now()
    const controller = new AbortController()
    abortRef.current = controller

    try {
      let url: string
      let headers: Record<string, string> = { "Content-Type": "application/json" }
      let bodyObj: Record<string, unknown>

      if (selectedModel === "custom") {
        // Direct call to external API
        url = `${customEndpoint.replace(/\/$/, "")}/chat/completions`
        if (customApiKey) headers["Authorization"] = `Bearer ${customApiKey}`
        bodyObj = {
          model: customModel,
          messages: allMessages,
          temperature,
          top_p: topP,
          max_tokens: maxTokens,
          stream: true,
        }
      } else {
        // Call backend server directly (bypass Next.js proxy to avoid SSE buffering)
        const colonIdx = selectedModel.indexOf(":")
        const serviceId = selectedModel.slice(0, colonIdx)
        const modelName = selectedModel.slice(colonIdx + 1)
        const serverHost = window.location.hostname
        url = `http://${serverHost}:4500/api/v1/workspace/workspaces/${workspaceId}/llm/chat`
        bodyObj = {
          _service_id: serviceId,
          model: modelName,
          messages: allMessages,
          temperature,
          top_p: topP,
          max_tokens: maxTokens,
          stream: true,
        }
      }

      const res = await fetch(url, {
        method: "POST",
        headers,
        body: JSON.stringify(bodyObj),
        signal: controller.signal,
      })

      if (!res.ok) {
        const err = await res.text()
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: `Error ${res.status}: ${err}` },
        ])
        return
      }

      const reader = res.body?.getReader()
      if (!reader) return

      const decoder = new TextDecoder()
      let fullText = ""
      let tokenCount = 0

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value, { stream: true })
        const lines = chunk.split("\n")

        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed.startsWith("data: ")) continue
          const data = trimmed.slice(6)
          if (data === "[DONE]") continue

          try {
            const parsed = JSON.parse(data)
            const delta = parsed.choices?.[0]?.delta?.content
            if (delta) {
              fullText += delta
              tokenCount++
              setStreamText(fullText)
            }
          } catch { /* ignore parse errors */ }
        }
      }

      setLastLatency(Date.now() - startTime)
      setLastTokens(tokenCount)
      setMessages((prev) => [...prev, { role: "assistant", content: fullText }])
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: `Error: ${(e as Error).message}` },
        ])
      }
    } finally {
      setStreamText("")
      setStreaming(false)
      abortRef.current = null
    }
  }, [input, streaming, messages, selectedModel, workspaceId, customEndpoint, customModel, customApiKey, systemPrompt, temperature, topP, maxTokens])

  const handleStop = () => { abortRef.current?.abort() }

  const handleClear = () => {
    setMessages([])
    setStreamText("")
    setLastLatency(null)
    setLastTokens(null)
  }

  const handleExport = () => {
    const content = messages.map((m) => `### ${m.role}\n${m.content}`).join("\n\n---\n\n")
    const blob = new Blob([content], { type: "text/markdown" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = "playground-chat.md"
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleCopyLast = () => {
    const last = messages.filter((m) => m.role === "assistant").pop()
    if (last) navigator.clipboard.writeText(last.content)
  }

  return (
    <div className="flex h-[calc(100vh-8rem)] gap-4">
      {/* Left: Chat */}
      <div className="flex flex-1 flex-col min-w-0">
        {/* Service selector bar */}
        <div className="flex items-center gap-2 pb-3 flex-wrap">
          <Select value={selectedModel} onValueChange={setSelectedModel}>
            <SelectTrigger className="h-9 w-[280px] text-sm">
              <SelectValue placeholder="Select model" />
            </SelectTrigger>
            <SelectContent>
              {llmModels.map((m) => (
                <SelectItem
                  key={`${m.service_id}:${m.model}`}
                  value={`${m.service_id}:${m.model}`}
                  className="text-sm"
                >
                  <span className="flex items-center gap-1.5">
                    <Sparkles className="h-3 w-3" />
                    {m.service_label} — {m.model}
                  </span>
                </SelectItem>
              ))}
              <SelectItem value="custom" className="text-sm">Custom Endpoint</SelectItem>
            </SelectContent>
          </Select>

          {selectedModel === "custom" && (
            <>
              <Input
                placeholder="https://api.openai.com/v1"
                value={customEndpoint}
                onChange={(e) => setCustomEndpoint(e.target.value)}
                className="h-9 w-[220px] text-sm"
              />
              <Input
                placeholder="Model name"
                value={customModel}
                onChange={(e) => setCustomModel(e.target.value)}
                className="h-9 w-[140px] text-sm"
              />
              <Input
                placeholder="API Key"
                type="password"
                value={customApiKey}
                onChange={(e) => setCustomApiKey(e.target.value)}
                className="h-9 w-[140px] text-sm"
              />
            </>
          )}

          <div className="ml-auto flex items-center gap-1">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant={showSettings ? "secondary" : "ghost"}
                  size="icon" className="h-8 w-8"
                  onClick={() => setShowSettings(!showSettings)}
                >
                  <Settings2 className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Parameters</TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="ghost" size="icon" className="h-8 w-8" onClick={handleCopyLast}>
                  <Copy className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Copy last response</TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="ghost" size="icon" className="h-8 w-8" onClick={handleExport}>
                  <Download className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Export chat</TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="ghost" size="icon" className="h-8 w-8" onClick={handleClear}>
                  <Trash2 className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Clear chat</TooltipContent>
            </Tooltip>
          </div>
        </div>

        {/* Chat messages */}
        <div className="flex-1 overflow-y-auto rounded-lg border bg-muted/20 p-4 space-y-4">
          {messages.length === 0 && !streamText && (
            <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
              <Sparkles className="h-10 w-10 mb-3 opacity-30" />
              <p className="text-sm">Start a conversation with your AI model</p>
              <p className="text-xs mt-1">
                {llmModels.length > 0
                  ? `${llmModels.length} model(s) available from your workspace`
                  : "Select a model or enter a custom endpoint above"}
              </p>
            </div>
          )}

          {messages.map((msg, i) =>
            msg.role === "user" ? (
              /* User: right-aligned */
              <div key={i} className="flex justify-end gap-3">
                <div className="max-w-[80%]">
                  <p className="text-xs font-medium text-muted-foreground mb-1 text-right">You</p>
                  <div className="rounded-2xl rounded-tr-sm bg-primary text-primary-foreground px-4 py-2 text-sm whitespace-pre-wrap break-words">
                    {msg.content}
                  </div>
                </div>
                <div className="shrink-0 h-7 w-7 rounded-full flex items-center justify-center bg-primary text-primary-foreground text-xs">
                  <User className="h-3.5 w-3.5" />
                </div>
              </div>
            ) : (
              /* Assistant: left-aligned */
              <div key={i} className="flex gap-3">
                <div className="shrink-0 h-7 w-7 rounded-full flex items-center justify-center bg-muted text-muted-foreground text-xs">
                  <Bot className="h-3.5 w-3.5" />
                </div>
                <div className="max-w-[80%] min-w-0">
                  <p className="text-xs font-medium text-muted-foreground mb-1">Assistant</p>
                  <div className="rounded-2xl rounded-tl-sm bg-muted/60 px-4 py-2 prose prose-sm max-w-none text-sm dark:prose-invert [&_pre]:overflow-x-auto [&_pre]:rounded-lg [&_pre]:bg-background [&_pre]:p-3 [&_pre]:text-sm [&_pre]:font-[D2Coding,monospace] [&_code]:text-sm [&_code]:font-[D2Coding,monospace] [&_p]:my-1.5">
                    <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[[rehypeHighlight, { detect: true }]]}>
                      {msg.content}
                    </ReactMarkdown>
                  </div>
                </div>
              </div>
            )
          )}

          {streaming && (
            <div className="flex gap-3">
              <div className="shrink-0 h-7 w-7 rounded-full flex items-center justify-center bg-muted text-muted-foreground">
                <Bot className="h-3.5 w-3.5" />
              </div>
              <div className="max-w-[80%] min-w-0">
                <p className="text-xs font-medium text-muted-foreground mb-1">Assistant</p>
                <div className="rounded-2xl rounded-tl-sm bg-muted/60 px-4 py-2 prose prose-sm max-w-none text-sm dark:prose-invert [&_pre]:overflow-x-auto [&_pre]:rounded-lg [&_pre]:bg-background [&_pre]:p-3 [&_pre]:text-sm [&_pre]:font-[D2Coding,monospace] [&_code]:text-sm [&_code]:font-[D2Coding,monospace] [&_p]:my-1.5">
                  {streamText ? (
                    <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[[rehypeHighlight, { detect: true }]]}>
                      {streamText}
                    </ReactMarkdown>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-muted-foreground"><Loader2 className="h-3 w-3 animate-spin" />Thinking...</span>
                  )}
                  {streamText && <span className="inline-block w-1.5 h-4 bg-foreground/70 animate-pulse ml-0.5 align-text-bottom" />}
                </div>
              </div>
            </div>
          )}

          <div ref={chatEndRef} />
        </div>

        {/* Input bar */}
        <div className="flex items-end gap-2 pt-3">
          <Textarea
            placeholder="Type your message... (Shift+Enter for newline)"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend() }
            }}
            className="min-h-[44px] max-h-[120px] resize-none text-sm"
            rows={1}
          />
          {streaming ? (
            <Button variant="destructive" size="icon" className="h-[44px] w-[44px] shrink-0" onClick={handleStop}>
              <StopCircle className="h-5 w-5" />
            </Button>
          ) : (
            <Button size="icon" className="h-[44px] w-[44px] shrink-0" onClick={handleSend} disabled={!input.trim()}>
              <Send className="h-5 w-5" />
            </Button>
          )}
        </div>

        {/* Status bar */}
        <div className="flex items-center justify-between pt-1 text-[10px] text-muted-foreground">
          <span>
            {messages.filter((m) => m.role !== "system").length} messages
            {streaming && " · streaming..."}
          </span>
          <span className="flex items-center gap-3">
            {lastTokens != null && <span>{lastTokens} tokens</span>}
            {lastLatency != null && <span>{(lastLatency / 1000).toFixed(1)}s</span>}
          </span>
        </div>
      </div>

      {/* Right: Settings panel */}
      {showSettings && (
        <Card className="w-[280px] shrink-0">
          <CardContent className="space-y-4 pt-4 text-sm">
            <div className="space-y-1.5">
              <Label className="text-sm">System Prompt</Label>
              <Textarea
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                className="text-sm min-h-[80px] resize-y"
                rows={3}
              />
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <Label className="text-sm">Temperature</Label>
                <span className="text-xs text-muted-foreground">{temperature}</span>
              </div>
              <input type="range" min="0" max="2" step="0.1" value={temperature}
                onChange={(e) => setTemperature(parseFloat(e.target.value))}
                className="w-full accent-primary" />
              <div className="flex justify-between text-[10px] text-muted-foreground">
                <span>Precise</span><span>Creative</span>
              </div>
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <Label className="text-sm">Top P</Label>
                <span className="text-xs text-muted-foreground">{topP}</span>
              </div>
              <input type="range" min="0" max="1" step="0.05" value={topP}
                onChange={(e) => setTopP(parseFloat(e.target.value))}
                className="w-full accent-primary" />
            </div>

            <div className="space-y-1.5">
              <Label className="text-sm">Max Tokens</Label>
              <Select value={String(maxTokens)} onValueChange={(v) => setMaxTokens(parseInt(v))}>
                <SelectTrigger className="h-9 text-sm"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="256" className="text-sm">256</SelectItem>
                  <SelectItem value="512" className="text-sm">512</SelectItem>
                  <SelectItem value="1024" className="text-sm">1,024</SelectItem>
                  <SelectItem value="2048" className="text-sm">2,048</SelectItem>
                  <SelectItem value="4096" className="text-sm">4,096</SelectItem>
                  <SelectItem value="8192" className="text-sm">8,192</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5 border-t pt-3">
              <Label className="text-sm">Presets</Label>
              <div className="flex flex-wrap gap-1.5">
                <Button variant="outline" size="sm" className="text-xs h-7"
                  onClick={() => { setTemperature(0.1); setTopP(0.9); setMaxTokens(2048) }}>Factual</Button>
                <Button variant="outline" size="sm" className="text-xs h-7"
                  onClick={() => { setTemperature(0.7); setTopP(0.9); setMaxTokens(2048) }}>Balanced</Button>
                <Button variant="outline" size="sm" className="text-xs h-7"
                  onClick={() => { setTemperature(1.2); setTopP(0.95); setMaxTokens(4096) }}>Creative</Button>
                <Button variant="outline" size="sm" className="text-xs h-7"
                  onClick={() => { setTemperature(0); setTopP(1); setMaxTokens(1024) }}>Deterministic</Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
