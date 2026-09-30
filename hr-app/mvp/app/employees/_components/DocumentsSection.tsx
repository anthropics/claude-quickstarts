"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";

export interface DocumentRow {
  id: number;
  title: string;
  category: string;
  original_name: string;
  size_bytes: number;
  file_id: number;
  uploaded_by_name: string | null;
  created_at: string;
}

const CATEGORIES: { value: string; label: string; badge: string }[] = [
  { value: "contract", label: "Contract", badge: "badge-blue" },
  { value: "id_document", label: "ID document", badge: "badge-yellow" },
  { value: "certificate", label: "Certificate", badge: "badge-green" },
  { value: "policy", label: "Policy", badge: "badge-gray" },
  { value: "other", label: "Other", badge: "badge-gray" },
];

function categoryBadge(value: string) {
  const cat = CATEGORIES.find((c) => c.value === value);
  return <span className={cat?.badge ?? "badge-gray"}>{cat?.label ?? value}</span>;
}

function fmtSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

interface Props {
  employeeId: number;
  documents: DocumentRow[];
  canUpload: boolean;
  canDelete: boolean;
}

export default function DocumentsSection({ employeeId, documents, canUpload, canDelete }: Props) {
  const router = useRouter();
  const formRef = useRef<HTMLFormElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  async function handleUpload(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);

    const fd = new FormData(e.currentTarget);
    const title = ((fd.get("title") as string | null) ?? "").trim();
    const category = (fd.get("category") as string | null) ?? "other";
    const file = fd.get("file");
    if (!title || !file || typeof file === "string" || file.size === 0) {
      setError("Title and file are required.");
      return;
    }

    setBusy(true);
    try {
      // 1. Upload the raw file, 2. attach it to this employee's vault.
      const uploadFd = new FormData();
      uploadFd.append("file", file);
      const uploadRes = await fetch("/api/files", { method: "POST", body: uploadFd });
      const uploaded = (await uploadRes.json()) as { id?: number; error?: string };
      if (!uploadRes.ok || !uploaded.id) {
        setError(uploaded.error ?? "Upload failed.");
        setBusy(false);
        return;
      }

      const metaRes = await fetch(`/api/employees/${employeeId}/documents`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_id: uploaded.id, title, category }),
      });
      const meta = (await metaRes.json()) as { id?: number; error?: string };
      if (!metaRes.ok) {
        setError(meta.error ?? "Could not save document.");
        setBusy(false);
        return;
      }

      formRef.current?.reset();
      setBusy(false);
      router.refresh();
    } catch {
      setError("Network error — please try again.");
      setBusy(false);
    }
  }

  async function handleDelete(docId: number, title: string) {
    if (!window.confirm(`Delete "${title}"? This cannot be undone.`)) return;
    setError(null);
    setDeletingId(docId);
    try {
      const res = await fetch(`/api/employees/${employeeId}/documents/${docId}`, { method: "DELETE" });
      if (!res.ok) {
        const data = (await res.json()) as { error?: string };
        setError(data.error ?? "Could not delete document.");
      } else {
        router.refresh();
      }
    } catch {
      setError("Network error — please try again.");
    }
    setDeletingId(null);
  }

  return (
    <div className="card">
      <h2 className="mb-3 font-semibold">Documents</h2>

      {error && (
        <div className="mb-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {documents.length === 0 ? (
        <p className="text-sm text-gray-500">No documents on file.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="th">Title</th>
                <th className="th">Category</th>
                <th className="th">File</th>
                <th className="th">Size</th>
                <th className="th">Uploaded by</th>
                <th className="th">Date</th>
                {canDelete && <th className="th" />}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {documents.map((doc) => (
                <tr key={doc.id}>
                  <td className="td font-medium text-gray-900">
                    <a
                      href={`/api/files/${doc.file_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-brand-600 hover:underline"
                    >
                      {doc.title}
                    </a>
                  </td>
                  <td className="td">{categoryBadge(doc.category)}</td>
                  <td className="td text-gray-500">{doc.original_name}</td>
                  <td className="td text-gray-500">{fmtSize(doc.size_bytes)}</td>
                  <td className="td">{doc.uploaded_by_name ?? "—"}</td>
                  <td className="td text-gray-500">{doc.created_at.slice(0, 10)}</td>
                  {canDelete && (
                    <td className="td text-right">
                      <button
                        type="button"
                        className="text-sm font-medium text-red-600 hover:underline disabled:opacity-50"
                        onClick={() => handleDelete(doc.id, doc.title)}
                        disabled={deletingId === doc.id}
                      >
                        {deletingId === doc.id ? "Deleting…" : "Delete"}
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {canUpload && (
        <form ref={formRef} onSubmit={handleUpload} className="mt-4 border-t border-gray-100 pt-4">
          <h3 className="mb-3 text-sm font-semibold text-gray-700">Upload document</h3>
          <div className="grid gap-4 sm:grid-cols-3">
            <div>
              <label className="label" htmlFor="doc_title">Title *</label>
              <input id="doc_title" name="title" className="input" required placeholder="e.g. Signed contract" />
            </div>
            <div>
              <label className="label" htmlFor="doc_category">Category *</label>
              <select id="doc_category" name="category" className="input" defaultValue="other">
                {CATEGORIES.map((c) => (
                  <option key={c.value} value={c.value}>{c.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="doc_file">File * (PDF, PNG, JPG, DOC, DOCX — max 5 MB)</label>
              <input id="doc_file" name="file" type="file" className="input" required accept=".pdf,.png,.jpg,.jpeg,.doc,.docx" />
            </div>
          </div>
          <button type="submit" className="btn-primary mt-4" disabled={busy}>
            {busy ? "Uploading…" : "Upload"}
          </button>
        </form>
      )}
    </div>
  );
}
