"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Plus, Database, Trash2, RefreshCw } from "lucide-react";
import {
  fetchCollections,
  createCollection,
  deleteCollection,
  triggerCollectionSync,
  type Collection,
} from "@/lib/api";
import { toast } from "sonner";

export default function CollectionsPage() {
  const [collections, setCollections] = useState<Collection[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");

  const load = () => fetchCollections().then(setCollections).catch(() => {});
  useEffect(() => { load(); }, []);

  const handleCreate = async () => {
    if (!newName.trim()) return;
    try {
      await createCollection({ name: newName, description: newDesc || undefined });
      toast.success("Collection created");
      setShowCreate(false);
      setNewName("");
      setNewDesc("");
      load();
    } catch (e: any) { toast.error(e.message); }
  };

  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`Delete "${name}"? All documents and embeddings will be removed.`)) return;
    try {
      await deleteCollection(id);
      toast.success("Deleted");
      load();
    } catch (e: any) { toast.error(e.message); }
  };

  const handleSync = async (id: number) => {
    try {
      toast.info("Sync started...");
      await triggerCollectionSync(id);
      toast.success("Sync complete");
      load();
    } catch (e: any) { toast.error(e.message); }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div />
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-[var(--radius)] text-sm font-medium"
          style={{ background: "var(--primary)", color: "var(--primary-foreground)" }}
        >
          <Plus className="h-4 w-4" /> New Collection
        </button>
      </div>

      {showCreate && (
        <div className="rounded-[var(--radius)] border p-4 space-y-3" style={{ background: "var(--card)" }}>
          <input
            placeholder="Collection name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            className="w-full rounded-[var(--radius)] border bg-transparent px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
          />
          <input
            placeholder="Description (optional)"
            value={newDesc}
            onChange={(e) => setNewDesc(e.target.value)}
            className="w-full rounded-[var(--radius)] border bg-transparent px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
          />
          <div className="flex gap-2">
            <button onClick={handleCreate} className="px-3 py-1.5 rounded-[var(--radius)] text-sm font-medium" style={{ background: "var(--primary)", color: "var(--primary-foreground)" }}>
              Create
            </button>
            <button onClick={() => setShowCreate(false)} className="px-3 py-1.5 rounded-[var(--radius)] border text-sm">
              Cancel
            </button>
          </div>
        </div>
      )}

      <div className="rounded-[var(--radius)] border" style={{ background: "var(--card)" }}>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-[var(--muted-foreground)] text-xs uppercase tracking-wider border-b">
              <th className="text-left px-4 py-3 font-medium">Name</th>
              <th className="text-left px-4 py-3 font-medium">Model</th>
              <th className="text-right px-4 py-3 font-medium">Docs</th>
              <th className="text-right px-4 py-3 font-medium">Chunks</th>
              <th className="text-left px-4 py-3 font-medium">Strategy</th>
              <th className="text-right px-4 py-3 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {collections.map((c) => (
              <tr key={c.id} className="border-t border-[var(--border)] hover:bg-[var(--accent)] transition-colors">
                <td className="px-4 py-3">
                  <Link href={`/dashboard/collections/${c.id}`} className="font-medium hover:underline" style={{ color: "var(--primary)" }}>
                    <Database className="inline h-3.5 w-3.5 mr-1.5" />
                    {c.name}
                  </Link>
                  {c.description && (
                    <div className="text-xs text-[var(--muted-foreground)] mt-0.5">{c.description}</div>
                  )}
                </td>
                <td className="px-4 py-3 text-xs text-[var(--muted-foreground)]">{c.embedding_model.split("/").pop()}</td>
                <td className="px-4 py-3 text-right font-medium">{c.document_count.toLocaleString()}</td>
                <td className="px-4 py-3 text-right font-medium">{c.chunk_count.toLocaleString()}</td>
                <td className="px-4 py-3">
                  <span className="inline-flex px-2 py-0.5 rounded-full text-xs font-medium bg-[var(--secondary)] text-[var(--secondary-foreground)]">
                    {c.chunk_strategy}
                  </span>
                </td>
                <td className="px-4 py-3 text-right space-x-1">
                  <button onClick={() => handleSync(c.id)} className="p-1.5 rounded-[var(--radius)] text-[var(--muted-foreground)] hover:bg-[var(--accent)]" title="Sync">
                    <RefreshCw className="h-4 w-4" />
                  </button>
                  <button onClick={() => handleDelete(c.id, c.name)} className="p-1.5 rounded-[var(--radius)] text-[var(--muted-foreground)] hover:text-[var(--destructive)]" title="Delete">
                    <Trash2 className="h-4 w-4" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {collections.length === 0 && (
          <div className="text-center py-12 text-[var(--muted-foreground)] text-sm">
            No collections yet. Create one to get started.
          </div>
        )}
      </div>
    </div>
  );
}
