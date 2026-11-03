"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

interface SendEmailFormProps {
  appId: number;
  candidateEmail: string;
}

const TEMPLATE_OPTIONS = [
  { value: "received", label: "Application received" },
  { value: "interview", label: "Interview invitation" },
  { value: "offer", label: "Offer" },
  { value: "rejection", label: "Rejection" },
];

export default function SendEmailForm({ appId, candidateEmail }: SendEmailFormProps) {
  const router = useRouter();
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSending(true);
    setError(null);
    setSent(null);

    const form = e.currentTarget;
    const data = new FormData(form);
    const template = data.get("template") as string;

    try {
      const res = await fetch(`/api/recruitment/applications/${appId}/email`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          template,
          custom_note: (data.get("custom_note") as string) || undefined,
        }),
      });
      const json = await res.json();
      if (!res.ok) {
        setError(json.error ?? "Failed to send email.");
        setSending(false);
        return;
      }
      setSent(TEMPLATE_OPTIONS.find((t) => t.value === template)?.label ?? template);
      form.reset();
      router.refresh();
    } catch {
      setError("Network error. Please try again.");
    }
    setSending(false);
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}
      {sent && (
        <div className="rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700">
          &ldquo;{sent}&rdquo; email queued to {candidateEmail}.
        </div>
      )}
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label className="label">Template</label>
          <select name="template" className="input" defaultValue="received">
            {TEMPLATE_OPTIONS.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-end">
          <p className="pb-2 text-xs text-gray-400">To: {candidateEmail}</p>
        </div>
      </div>
      <div>
        <label className="label">Personal note (optional)</label>
        <textarea
          name="custom_note"
          rows={2}
          className="input resize-y"
          placeholder="Added to the end of the template…"
        />
      </div>
      <button type="submit" disabled={sending} className="btn-secondary text-sm">
        {sending ? "Sending…" : "Send email"}
      </button>
    </form>
  );
}
