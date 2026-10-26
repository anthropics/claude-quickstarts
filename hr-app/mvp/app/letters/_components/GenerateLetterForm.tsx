"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

interface Props {
  templates: { id: number; name: string; type: string }[];
  employees: { id: number; name: string; employee_number: string }[];
  initialEmployeeId: number | null;
}

interface Preview {
  title: string;
  content: string;
}

export default function GenerateLetterForm({ templates, employees, initialEmployeeId }: Props) {
  const router = useRouter();
  const [templateId, setTemplateId] = useState<string>(templates[0] ? String(templates[0].id) : "");
  const [employeeId, setEmployeeId] = useState<string>(initialEmployeeId ? String(initialEmployeeId) : "");
  const [reason, setReason] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function post(confirm: boolean) {
    setError(null);
    if (!templateId || !employeeId) {
      setError("Select a template and an employee.");
      return;
    }
    setBusy(true);
    try {
      const res = await fetch("/api/letters/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          template_id: Number(templateId),
          employee_id: Number(employeeId),
          reason: reason.trim() || undefined,
          confirm,
        }),
      });
      const data = (await res.json()) as { id?: number; title?: string; content?: string; error?: string };
      if (!res.ok) {
        setError(data.error ?? "Something went wrong.");
        setBusy(false);
        return;
      }
      if (confirm && data.id) {
        router.push(`/letters/${data.id}`);
        router.refresh();
        return;
      }
      setPreview({ title: data.title ?? "", content: data.content ?? "" });
      setBusy(false);
    } catch {
      setError("Network error — please try again.");
      setBusy(false);
    }
  }

  const selectedTemplate = templates.find((t) => String(t.id) === templateId);

  return (
    <div className="space-y-6">
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
      )}

      <div className="card">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="label" htmlFor="template_id">Template *</label>
            <select
              id="template_id"
              className="input"
              value={templateId}
              onChange={(e) => {
                setTemplateId(e.target.value);
                setPreview(null);
              }}
            >
              {templates.map((t) => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="employee_id">Employee *</label>
            <select
              id="employee_id"
              className="input"
              value={employeeId}
              onChange={(e) => {
                setEmployeeId(e.target.value);
                setPreview(null);
              }}
            >
              <option value="">Select employee…</option>
              {employees.map((e) => (
                <option key={e.id} value={e.id}>
                  {e.name} ({e.employee_number})
                </option>
              ))}
            </select>
          </div>
          <div className="sm:col-span-2">
            <label className="label" htmlFor="reason">
              Reason {selectedTemplate?.type === "warning" ? "* (used by the warning template)" : "(optional — fills {{reason}})"}
            </label>
            <textarea
              id="reason"
              className="input"
              rows={2}
              value={reason}
              placeholder="e.g. repeated late arrival on 1, 2 and 3 July 2026"
              onChange={(e) => {
                setReason(e.target.value);
                setPreview(null);
              }}
            />
          </div>
        </div>
        <div className="mt-4 flex gap-3">
          <button type="button" className="btn-primary" onClick={() => post(false)} disabled={busy}>
            {busy && !preview ? "Rendering…" : "Preview"}
          </button>
        </div>
      </div>

      {preview && (
        <div className="card">
          <h2 className="mb-1 font-semibold">Preview</h2>
          <p className="mb-4 text-sm text-gray-500">
            Nothing has been saved yet. Review the letter below, then confirm to issue it.
          </p>
          <div className="rounded-lg border border-gray-200 bg-gray-50 p-6">
            <p className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-500">{preview.title}</p>
            {/* Rendered as a text node on purpose — template output is plain text. */}
            <p className="whitespace-pre-line text-sm leading-relaxed text-gray-800">{preview.content}</p>
          </div>
          <div className="mt-4 flex gap-3">
            <button type="button" className="btn-primary" onClick={() => post(true)} disabled={busy}>
              {busy ? "Issuing…" : "Confirm & issue letter"}
            </button>
            <button type="button" className="btn-secondary" onClick={() => setPreview(null)} disabled={busy}>
              Back
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
