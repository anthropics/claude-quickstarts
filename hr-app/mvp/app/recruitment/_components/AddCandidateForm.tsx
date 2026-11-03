"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

interface AddCandidateFormProps {
  postingId: number;
}

export default function AddCandidateForm({ postingId }: AddCandidateFormProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSaving(true);
    setError(null);

    const form = e.currentTarget;
    const data = new FormData(form);

    // Upload the CV first (authenticated file store), then link its id.
    let cvFileId: number | null = null;
    const cv = data.get("cv");
    if (cv && typeof cv !== "string" && cv.size > 0) {
      const uploadData = new FormData();
      uploadData.set("file", cv);
      try {
        const uploadRes = await fetch("/api/files", { method: "POST", body: uploadData });
        const uploadJson = await uploadRes.json();
        if (!uploadRes.ok) {
          setError(uploadJson.error ?? "CV upload failed.");
          setSaving(false);
          return;
        }
        cvFileId = uploadJson.id;
      } catch {
        setError("CV upload failed. Please try again.");
        setSaving(false);
        return;
      }
    }

    const payload = {
      first_name: data.get("first_name") as string,
      last_name: data.get("last_name") as string,
      email: data.get("email") as string,
      phone: data.get("phone") as string || null,
      cv_file_id: cvFileId,
      source: data.get("source") as string,
      job_posting_id: postingId,
    };

    try {
      const res = await fetch("/api/recruitment/candidates", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const json = await res.json();
      if (!res.ok) {
        setError(json.error ?? "Failed to add candidate.");
        setSaving(false);
        return;
      }
      form.reset();
      setOpen(false);
      router.refresh();
    } catch {
      setError("Network error. Please try again.");
    }
    setSaving(false);
  }

  return (
    <div>
      {!open ? (
        <button onClick={() => setOpen(true)} className="btn-secondary text-sm">
          + Add candidate
        </button>
      ) : (
        <div className="card mt-4 max-w-xl border-brand-200">
          <h3 className="mb-4 font-semibold">Add candidate manually</h3>
          {error && (
            <div className="mb-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <label className="label">First name *</label>
                <input name="first_name" required className="input" />
              </div>
              <div>
                <label className="label">Last name *</label>
                <input name="last_name" required className="input" />
              </div>
            </div>
            <div>
              <label className="label">Email *</label>
              <input name="email" type="email" required className="input" />
            </div>
            <div>
              <label className="label">Phone</label>
              <input name="phone" className="input" />
            </div>
            <div>
              <label className="label">CV file</label>
              <input
                name="cv"
                type="file"
                accept=".pdf,.doc,.docx,.png,.jpg,.jpeg,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,image/png,image/jpeg"
                className="block w-full text-sm text-gray-600 file:mr-3 file:rounded-lg file:border-0 file:bg-gray-100 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-gray-700 hover:file:bg-gray-200"
              />
              <p className="mt-1 text-xs text-gray-400">PDF, DOC, DOCX, PNG or JPG — up to 5 MB.</p>
            </div>
            <div>
              <label className="label">Source</label>
              <select name="source" className="input" defaultValue="direct">
                <option value="direct">Direct</option>
                <option value="linkedin">LinkedIn</option>
                <option value="indeed">Indeed</option>
                <option value="referral">Referral</option>
                <option value="internal">Internal</option>
              </select>
            </div>
            <div className="flex gap-2 pt-1">
              <button type="submit" disabled={saving} className="btn-primary">
                {saving ? "Saving…" : "Add candidate"}
              </button>
              <button
                type="button"
                onClick={() => { setOpen(false); setError(null); }}
                className="btn-secondary"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
