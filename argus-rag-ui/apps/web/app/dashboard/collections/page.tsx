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

  useEffect(() => {
    load();
  }, []);

  const handleCreate = async () => {
    if (!newName.trim()) return;
    try {
      await createCollection({ name: newName, description: newDesc || undefined });
      toast.success("Collection created");
      setShowCreate(false);
      setNewName("");
      setNewDesc("");
      load();
    } catch (e: any) {
      toast.error(e.message);
    }
  };

  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`Delete collection "${name}"? This will remove all documents and embeddings.`))
      return;
    try {
      await deleteCollection(id);
      toast.success("Collection deleted");
      load();
    } catch (e: any) {
      toast.error(e.message);
    }
  };

  const handleSync = async (id: number) => {
    try {
      toast.info("Sync started...");
      const result = await triggerCollectionSync(id);
      toast.success(`Sync complete: ${result.syncs?.length || 0} sources`);
      load();
    } catch (e: any) {
      toast.error(e.message);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Collections</h1>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md text-sm hover:bg-blue-700"
        >
          <Plus className="h-4 w-4" /> New Collection
        </button>
      </div>

      {/* Create dialog */}
      {showCreate && (
        <div className="border rounded-lg p-4 bg-gray-50 dark:bg-gray-800 space-y-3">
          <input
            placeholder="Collection name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            className="w-full border rounded px-3 py-2 text-sm"
          />
          <input
            placeholder="Description (optional)"
            value={newDesc}
            onChange={(e) => setNewDesc(e.target.value)}
            className="w-full border rounded px-3 py-2 text-sm"
          />
          <div className="flex gap-2">
            <button
              onClick={handleCreate}
              className="px-4 py-2 bg-blue-600 text-white rounded text-sm"
            >
              Create
            </button>
            <button
              onClick={() => setShowCreate(false)}
              className="px-4 py-2 border rounded text-sm"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Table */}
      <table className="w-full text-sm">
        <thead className="text-gray-500 border-b">
          <tr>
            <th className="text-left py-2">Name</th>
            <th className="text-left py-2">Model</th>
            <th className="text-right py-2">Docs</th>
            <th className="text-right py-2">Chunks</th>
            <th className="text-left py-2">Strategy</th>
            <th className="text-left py-2">Updated</th>
            <th className="text-right py-2">Actions</th>
          </tr>
        </thead>
        <tbody>
          {collections.map((c) => (
            <tr key={c.id} className="border-b hover:bg-gray-50 dark:hover:bg-gray-800">
              <td className="py-2">
                <Link
                  href={`/dashboard/collections/${c.id}`}
                  className="text-blue-600 hover:underline font-medium"
                >
                  <Database className="inline h-4 w-4 mr-1" />
                  {c.name}
                </Link>
                {c.description && (
                  <span className="text-gray-400 ml-2 text-xs">{c.description}</span>
                )}
              </td>
              <td className="py-2 text-xs text-gray-500">{c.embedding_model}</td>
              <td className="py-2 text-right">{c.document_count}</td>
              <td className="py-2 text-right">{c.chunk_count}</td>
              <td className="py-2">{c.chunk_strategy}</td>
              <td className="py-2 text-gray-500 text-xs">
                {new Date(c.updated_at).toLocaleDateString()}
              </td>
              <td className="py-2 text-right space-x-1">
                <button
                  onClick={() => handleSync(c.id)}
                  className="p-1 text-gray-500 hover:text-blue-600"
                  title="Sync"
                >
                  <RefreshCw className="h-4 w-4" />
                </button>
                <button
                  onClick={() => handleDelete(c.id, c.name)}
                  className="p-1 text-gray-500 hover:text-red-600"
                  title="Delete"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {collections.length === 0 && (
        <p className="text-gray-500 text-center py-8">No collections yet. Create one to get started.</p>
      )}
    </div>
  );
}
