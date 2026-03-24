"use client";

import { useEffect, useState } from "react";
import {
  fetchEmbeddingSettings,
  updateEmbeddingSettings,
  fetchChunkingSettings,
  updateChunkingSettings,
  type EmbeddingSettings,
  type ChunkingSettings,
} from "@/lib/api";
import { toast } from "sonner";

export default function SettingsPage() {
  const [emb, setEmb] = useState<EmbeddingSettings | null>(null);
  const [chunk, setChunk] = useState<ChunkingSettings | null>(null);
  const [embForm, setEmbForm] = useState({ provider: "", model: "", api_key: "", api_url: "" });
  const [chunkForm, setChunkForm] = useState({ default_strategy: "", max_chunk_size: 512, min_chunk_size: 50, overlap: 50 });

  useEffect(() => {
    fetchEmbeddingSettings().then((s) => {
      setEmb(s);
      setEmbForm({ provider: s.provider, model: s.model, api_key: "", api_url: s.api_url });
    }).catch(() => {});
    fetchChunkingSettings().then((s) => {
      setChunk(s);
      setChunkForm(s);
    }).catch(() => {});
  }, []);

  const saveEmbedding = async () => {
    try {
      const result = await updateEmbeddingSettings(embForm);
      setEmb(result);
      toast.success("Embedding settings saved");
    } catch (e: any) {
      toast.error(e.message);
    }
  };

  const saveChunking = async () => {
    try {
      const result = await updateChunkingSettings(chunkForm);
      setChunk(result);
      toast.success("Chunking settings saved");
    } catch (e: any) {
      toast.error(e.message);
    }
  };

  return (
    <div className="space-y-8 max-w-2xl">
      <h1 className="text-2xl font-bold">Settings</h1>

      {/* Embedding */}
      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Embedding Model</h2>
        {emb && (
          <p className="text-sm text-gray-500">
            Current: {emb.provider} / {emb.model} ({emb.dimension}dim)
          </p>
        )}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-gray-500">Provider</label>
            <select
              value={embForm.provider}
              onChange={(e) => setEmbForm({ ...embForm, provider: e.target.value })}
              className="w-full border rounded px-3 py-2 text-sm"
            >
              <option value="local">Local (SentenceTransformer)</option>
              <option value="openai">OpenAI</option>
              <option value="ollama">Ollama</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-500">Model</label>
            <input
              value={embForm.model}
              onChange={(e) => setEmbForm({ ...embForm, model: e.target.value })}
              className="w-full border rounded px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="text-xs text-gray-500">API Key</label>
            <input
              type="password"
              value={embForm.api_key}
              onChange={(e) => setEmbForm({ ...embForm, api_key: e.target.value })}
              className="w-full border rounded px-3 py-2 text-sm"
              placeholder="Empty for local/Ollama"
            />
          </div>
          <div>
            <label className="text-xs text-gray-500">API URL</label>
            <input
              value={embForm.api_url}
              onChange={(e) => setEmbForm({ ...embForm, api_url: e.target.value })}
              className="w-full border rounded px-3 py-2 text-sm"
              placeholder="http://localhost:11434"
            />
          </div>
        </div>
        <button onClick={saveEmbedding} className="px-4 py-2 bg-blue-600 text-white rounded text-sm">
          Save Embedding Settings
        </button>
      </section>

      {/* Chunking */}
      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Default Chunking</h2>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-gray-500">Strategy</label>
            <select
              value={chunkForm.default_strategy}
              onChange={(e) => setChunkForm({ ...chunkForm, default_strategy: e.target.value })}
              className="w-full border rounded px-3 py-2 text-sm"
            >
              <option value="single">Single (no split)</option>
              <option value="paragraph">Paragraph</option>
              <option value="fixed">Fixed size</option>
              <option value="sliding">Sliding window</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-500">Max Chunk Size</label>
            <input
              type="number"
              value={chunkForm.max_chunk_size}
              onChange={(e) => setChunkForm({ ...chunkForm, max_chunk_size: Number(e.target.value) })}
              className="w-full border rounded px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="text-xs text-gray-500">Min Chunk Size</label>
            <input
              type="number"
              value={chunkForm.min_chunk_size}
              onChange={(e) => setChunkForm({ ...chunkForm, min_chunk_size: Number(e.target.value) })}
              className="w-full border rounded px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="text-xs text-gray-500">Overlap</label>
            <input
              type="number"
              value={chunkForm.overlap}
              onChange={(e) => setChunkForm({ ...chunkForm, overlap: Number(e.target.value) })}
              className="w-full border rounded px-3 py-2 text-sm"
            />
          </div>
        </div>
        <button onClick={saveChunking} className="px-4 py-2 bg-blue-600 text-white rounded text-sm">
          Save Chunking Settings
        </button>
      </section>
    </div>
  );
}
