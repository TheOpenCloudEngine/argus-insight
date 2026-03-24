"use client";

import { useEffect, useState } from "react";
import {
  fetchEmbeddingSettings, updateEmbeddingSettings,
  fetchChunkingSettings, updateChunkingSettings,
  type EmbeddingSettings, type ChunkingSettings,
} from "@/lib/api";
import { toast } from "sonner";

export default function SettingsPage() {
  const [emb, setEmb] = useState<EmbeddingSettings | null>(null);
  const [chunk, setChunk] = useState<ChunkingSettings | null>(null);
  const [embForm, setEmbForm] = useState({ provider: "", model: "", api_key: "", api_url: "" });
  const [chunkForm, setChunkForm] = useState({ default_strategy: "", max_chunk_size: 512, min_chunk_size: 50, overlap: 50 });

  useEffect(() => {
    fetchEmbeddingSettings().then((s) => { setEmb(s); setEmbForm({ provider: s.provider, model: s.model, api_key: "", api_url: s.api_url }); }).catch(() => {});
    fetchChunkingSettings().then((s) => { setChunk(s); setChunkForm(s); }).catch(() => {});
  }, []);

  const saveEmb = async () => {
    try { const r = await updateEmbeddingSettings(embForm); setEmb(r); toast.success("Saved"); }
    catch (e: any) { toast.error(e.message); }
  };
  const saveChunk = async () => {
    try { const r = await updateChunkingSettings(chunkForm); setChunk(r); toast.success("Saved"); }
    catch (e: any) { toast.error(e.message); }
  };

  const inputCls = "w-full rounded-[var(--radius)] border bg-transparent px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]";
  const labelCls = "text-xs font-medium text-[var(--muted-foreground)]";

  return (
    <div className="space-y-8 max-w-2xl">
      {/* Embedding */}
      <div className="rounded-[var(--radius)] border" style={{ background: "var(--card)" }}>
        <div className="px-4 py-3 border-b"><h2 className="text-sm font-semibold">Embedding Model</h2></div>
        <div className="p-4 space-y-3">
          {emb && <p className="text-xs text-[var(--muted-foreground)]">Current: {emb.provider} / {emb.model} ({emb.dimension}dim)</p>}
          <div className="grid grid-cols-2 gap-3">
            <div><label className={labelCls}>Provider</label>
              <select value={embForm.provider} onChange={(e) => setEmbForm({ ...embForm, provider: e.target.value })} className={inputCls}>
                <option value="local">Local (SentenceTransformer)</option>
                <option value="openai">OpenAI</option>
                <option value="ollama">Ollama</option>
              </select></div>
            <div><label className={labelCls}>Model</label>
              <input value={embForm.model} onChange={(e) => setEmbForm({ ...embForm, model: e.target.value })} className={inputCls} /></div>
            <div><label className={labelCls}>API Key</label>
              <input type="password" value={embForm.api_key} onChange={(e) => setEmbForm({ ...embForm, api_key: e.target.value })} className={inputCls} placeholder="Empty for local" /></div>
            <div><label className={labelCls}>API URL</label>
              <input value={embForm.api_url} onChange={(e) => setEmbForm({ ...embForm, api_url: e.target.value })} className={inputCls} placeholder="http://localhost:11434" /></div>
          </div>
          <button onClick={saveEmb} className="px-3 py-1.5 rounded-[var(--radius)] text-sm font-medium" style={{ background: "var(--primary)", color: "var(--primary-foreground)" }}>Save</button>
        </div>
      </div>

      {/* Chunking */}
      <div className="rounded-[var(--radius)] border" style={{ background: "var(--card)" }}>
        <div className="px-4 py-3 border-b"><h2 className="text-sm font-semibold">Default Chunking</h2></div>
        <div className="p-4 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div><label className={labelCls}>Strategy</label>
              <select value={chunkForm.default_strategy} onChange={(e) => setChunkForm({ ...chunkForm, default_strategy: e.target.value })} className={inputCls}>
                <option value="single">Single</option>
                <option value="paragraph">Paragraph</option>
                <option value="fixed">Fixed size</option>
                <option value="sliding">Sliding window</option>
              </select></div>
            <div><label className={labelCls}>Max Size</label>
              <input type="number" value={chunkForm.max_chunk_size} onChange={(e) => setChunkForm({ ...chunkForm, max_chunk_size: Number(e.target.value) })} className={inputCls} /></div>
            <div><label className={labelCls}>Min Size</label>
              <input type="number" value={chunkForm.min_chunk_size} onChange={(e) => setChunkForm({ ...chunkForm, min_chunk_size: Number(e.target.value) })} className={inputCls} /></div>
            <div><label className={labelCls}>Overlap</label>
              <input type="number" value={chunkForm.overlap} onChange={(e) => setChunkForm({ ...chunkForm, overlap: Number(e.target.value) })} className={inputCls} /></div>
          </div>
          <button onClick={saveChunk} className="px-3 py-1.5 rounded-[var(--radius)] text-sm font-medium" style={{ background: "var(--primary)", color: "var(--primary-foreground)" }}>Save</button>
        </div>
      </div>
    </div>
  );
}
