"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

interface Props {
  reviewId: number;
  initialStrengths: string | null;
  initialImprovements: string | null;
  initialComments: string | null;
  initialRating: number | null;
}

export default function ReviewForm({
  reviewId,
  initialStrengths,
  initialImprovements,
  initialComments,
  initialRating,
}: Props) {
  const router = useRouter();
  const [strengths, setStrengths] = useState(initialStrengths ?? "");
  const [improvements, setImprovements] = useState(initialImprovements ?? "");
  const [comments, setComments] = useState(initialComments ?? "");
  const [rating, setRating] = useState<number | null>(initialRating);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function save(action: "save" | "submit") {
    if (action === "submit" && rating === null) {
      setError("Please select a rating before submitting.");
      return;
    }
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      const res = await fetch(`/api/performance/reviews/${reviewId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action,
          strengths: strengths || null,
          improvements: improvements || null,
          overall_comments: comments || null,
          rating,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? "Something went wrong.");
        return;
      }
      if (action === "save") setNotice("Draft saved.");
      router.refresh();
    } catch {
      setError("Network error — please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      className="card space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        save("submit");
      }}
    >
      <h2 className="font-semibold">Write review</h2>
      <div>
        <label className="label" htmlFor="rv-strengths">Strengths</label>
        <textarea
          id="rv-strengths"
          className="input"
          rows={4}
          value={strengths}
          onChange={(e) => setStrengths(e.target.value)}
          placeholder="What went well this period?"
        />
      </div>
      <div>
        <label className="label" htmlFor="rv-improvements">Areas for improvement</label>
        <textarea
          id="rv-improvements"
          className="input"
          rows={4}
          value={improvements}
          onChange={(e) => setImprovements(e.target.value)}
          placeholder="Where is there room to grow?"
        />
      </div>
      <div>
        <label className="label" htmlFor="rv-comments">Overall comments</label>
        <textarea
          id="rv-comments"
          className="input"
          rows={3}
          value={comments}
          onChange={(e) => setComments(e.target.value)}
        />
      </div>
      <div>
        <span className="label">Rating</span>
        <div className="flex items-center gap-1" role="radiogroup" aria-label="Rating from 1 to 5">
          {[1, 2, 3, 4, 5].map((n) => (
            <button
              key={n}
              type="button"
              role="radio"
              aria-checked={rating === n}
              aria-label={`${n} out of 5`}
              className={`text-2xl transition-colors ${rating !== null && n <= rating ? "text-yellow-400" : "text-gray-300 hover:text-yellow-300"}`}
              onClick={() => setRating(n)}
            >
              ★
            </button>
          ))}
          <span className="ml-2 text-sm text-gray-500">{rating !== null ? `${rating} / 5` : "No rating yet"}</span>
        </div>
      </div>
      {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      {notice && <p className="rounded-lg bg-green-50 px-3 py-2 text-sm text-green-700">{notice}</p>}
      <div className="flex gap-2">
        <button type="button" className="btn-secondary" onClick={() => save("save")} disabled={busy}>
          {busy ? "Saving…" : "Save draft"}
        </button>
        <button type="submit" className="btn-primary" disabled={busy}>
          {busy ? "Saving…" : "Submit review"}
        </button>
      </div>
      <p className="text-xs text-gray-400">Once submitted, the review can no longer be edited.</p>
    </form>
  );
}
