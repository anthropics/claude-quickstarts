"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

interface ActionItem {
  text: string;
  done: boolean;
}

interface Props {
  meetingId: number;
  initialAgenda: string | null;
  initialNotes: string | null;
  initialActionItems: ActionItem[];
  status: "scheduled" | "completed" | "cancelled";
}

export default function OneOnOneEditor({ meetingId, initialAgenda, initialNotes, initialActionItems, status }: Props) {
  const router = useRouter();
  const [agenda, setAgenda] = useState(initialAgenda ?? "");
  const [notes, setNotes] = useState(initialNotes ?? "");
  const [items, setItems] = useState<ActionItem[]>(initialActionItems);
  const [newItem, setNewItem] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function patch(body: Record<string, unknown>, successNotice?: string) {
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      const res = await fetch(`/api/performance/one-on-ones/${meetingId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? "Something went wrong.");
        return;
      }
      if (successNotice) setNotice(successNotice);
      router.refresh();
    } catch {
      setError("Network error — please try again.");
    } finally {
      setBusy(false);
    }
  }

  function toggleItem(index: number) {
    const next = items.map((it, i) => (i === index ? { ...it, done: !it.done } : it));
    setItems(next);
    void patch({ action_items: next });
  }

  function removeItem(index: number) {
    const next = items.filter((_, i) => i !== index);
    setItems(next);
    void patch({ action_items: next });
  }

  function addItem(e: React.FormEvent) {
    e.preventDefault();
    const text = newItem.trim();
    if (!text) return;
    const next = [...items, { text, done: false }];
    setItems(next);
    setNewItem("");
    void patch({ action_items: next });
  }

  return (
    <div className="space-y-6">
      <div className="card space-y-4">
        <h2 className="font-semibold">Agenda &amp; notes</h2>
        <div>
          <label className="label" htmlFor="oo-edit-agenda">Agenda</label>
          <textarea
            id="oo-edit-agenda"
            className="input"
            rows={3}
            value={agenda}
            onChange={(e) => setAgenda(e.target.value)}
            placeholder="Topics to discuss…"
          />
        </div>
        <div>
          <label className="label" htmlFor="oo-edit-notes">Notes</label>
          <textarea
            id="oo-edit-notes"
            className="input"
            rows={4}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Discussion notes…"
          />
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            className="btn-primary text-sm"
            onClick={() => patch({ agenda: agenda || null, notes: notes || null }, "Saved.")}
            disabled={busy}
          >
            {busy ? "Saving…" : "Save"}
          </button>
          {status === "scheduled" && (
            <>
              <button
                className="btn-secondary text-sm"
                onClick={() => patch({ status: "completed", agenda: agenda || null, notes: notes || null })}
                disabled={busy}
              >
                Mark completed
              </button>
              <button
                className="btn-danger text-sm"
                onClick={() => patch({ status: "cancelled" })}
                disabled={busy}
              >
                Cancel meeting
              </button>
            </>
          )}
        </div>
        {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
        {notice && <p className="rounded-lg bg-green-50 px-3 py-2 text-sm text-green-700">{notice}</p>}
      </div>

      <div className="card space-y-3">
        <h2 className="font-semibold">Action items</h2>
        {items.length === 0 && <p className="text-sm text-gray-500">No action items yet.</p>}
        <ul className="space-y-2">
          {items.map((item, i) => (
            <li key={i} className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={item.done}
                onChange={() => toggleItem(i)}
                aria-label={`Mark "${item.text}" ${item.done ? "not done" : "done"}`}
              />
              <span className={item.done ? "text-gray-400 line-through" : "text-gray-700"}>{item.text}</span>
              <button
                className="ml-auto text-xs text-gray-400 hover:text-red-600"
                onClick={() => removeItem(i)}
                aria-label={`Remove "${item.text}"`}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
        <form onSubmit={addItem} className="flex gap-2">
          <input
            className="input flex-1"
            value={newItem}
            onChange={(e) => setNewItem(e.target.value)}
            placeholder="Add an action item…"
            aria-label="New action item"
          />
          <button type="submit" className="btn-secondary text-sm" disabled={busy || !newItem.trim()}>
            Add
          </button>
        </form>
      </div>
    </div>
  );
}
