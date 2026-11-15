"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

interface NotesEditorProps {
  appId: number;
  initialNotes: string | null;
}

export default function NotesEditor({ appId, initialNotes }: NotesEditorProps) {
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  const [notes, setNotes] = useState(initialNotes ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const res = await fetch(`/api/recruitment/applications/${appId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ notes }),
      });
      const json = await res.json();
      if (!res.ok) {
        setError(json.error ?? "Failed.");
        setSaving(false);
        return;
      }
      setEditing(false);
      router.refresh();
    } catch {
      setError("Network error.");
    }
    setSaving(false);
  }

  return (
    <div>
      <div className="mb-1 flex items-center justify-between">
        <h3 className="font-semibold">Notes</h3>
        {!editing && (
          <button onClick={() => setEditing(true)} className="text-xs text-brand-600 hover:underline">
            {notes ? "Edit" : "Add notes"}
          </button>
        )}
      </div>
      {!editing ? (
        <p className="text-sm text-gray-600 whitespace-pre-wrap">
          {notes || <span className="italic text-gray-400">No notes yet.</span>}
        </p>
      ) : (
        <div className="space-y-2">
          {error && <p className="text-xs text-red-600">{error}</p>}
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={4}
            className="input resize-y"
          />
          <div className="flex gap-2">
            <button onClick={save} disabled={saving} className="btn-primary text-sm">
              {saving ? "Saving…" : "Save"}
            </button>
            <button onClick={() => { setEditing(false); setNotes(initialNotes ?? ""); }} className="btn-secondary text-sm">
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
