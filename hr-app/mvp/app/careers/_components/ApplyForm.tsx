"use client";

import { useState } from "react";

interface ApplyFormProps {
  slug: string;
  jobTitle: string;
}

export default function ApplyForm({ slug, jobTitle }: ApplyFormProps) {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    const form = e.currentTarget;
    const data = new FormData(form);
    data.set("slug", slug);

    const cv = data.get("cv");
    if (!cv || typeof cv === "string" || cv.size === 0) {
      setError("Please attach your CV.");
      setSubmitting(false);
      return;
    }

    try {
      const res = await fetch("/api/careers/apply", { method: "POST", body: data });
      const json = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(json.error ?? "Something went wrong. Please try again.");
        setSubmitting(false);
        return;
      }
      setSubmitted(true);
    } catch {
      setError("Network error. Please check your connection and try again.");
    }
    setSubmitting(false);
  }

  if (submitted) {
    return (
      <div className="rounded-lg border border-green-200 bg-green-50 p-6 text-center">
        <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-green-100 text-xl text-green-700">
          ✓
        </div>
        <h3 className="font-semibold text-green-800">Application received</h3>
        <p className="mt-1 text-sm text-green-700">
          Thank you for applying for the {jobTitle} position. Our recruitment team
          will review your application and be in touch.
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label className="label" htmlFor="apply-first-name">First name *</label>
          <input id="apply-first-name" name="first_name" required className="input" autoComplete="given-name" />
        </div>
        <div>
          <label className="label" htmlFor="apply-last-name">Last name *</label>
          <input id="apply-last-name" name="last_name" required className="input" autoComplete="family-name" />
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label className="label" htmlFor="apply-email">Email *</label>
          <input id="apply-email" name="email" type="email" required className="input" autoComplete="email" />
        </div>
        <div>
          <label className="label" htmlFor="apply-phone">Phone</label>
          <input id="apply-phone" name="phone" type="tel" className="input" autoComplete="tel" />
        </div>
      </div>

      <div>
        <label className="label" htmlFor="apply-cv">CV / Resume *</label>
        <input
          id="apply-cv"
          name="cv"
          type="file"
          required
          accept=".pdf,.doc,.docx,.png,.jpg,.jpeg,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,image/png,image/jpeg"
          className="block w-full text-sm text-gray-600 file:mr-3 file:rounded-lg file:border-0 file:bg-brand-600 file:px-3 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-brand-700"
        />
        <p className="mt-1 text-xs text-gray-400">PDF, DOC, DOCX, PNG or JPG — up to 5 MB.</p>
      </div>

      {/* Honeypot: hidden from humans; bots that fill it are rejected. */}
      <div className="absolute -left-[9999px] top-auto h-px w-px overflow-hidden" aria-hidden="true">
        <label htmlFor="apply-website">Website</label>
        <input id="apply-website" name="website" type="text" tabIndex={-1} autoComplete="off" />
      </div>

      <button type="submit" disabled={submitting} className="btn-primary">
        {submitting ? "Submitting…" : "Submit application"}
      </button>
    </form>
  );
}
