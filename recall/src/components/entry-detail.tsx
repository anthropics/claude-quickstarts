"use client";

import { useState } from "react";
import Image from "next/image";
import {
  X,
  ExternalLink,
  Trash2,
  Calendar,
  BookOpen,
  Film,
  Tv,
  Podcast,
  Disc3,
  Music,
  Youtube,
  FileText,
  Ticket,
  MoreHorizontal,
} from "lucide-react";
import { toast } from "sonner";
import { MediaTypeBadge } from "@/components/media-type-badge";
import { StarRating } from "@/components/star-rating";
import type { Entry } from "@/lib/types";
import { MEDIA_TYPE_CONFIG } from "@/lib/types";
import { format, parseISO } from "date-fns";

const ICON_MAP: Record<
  string,
  React.ComponentType<{
    size?: number;
    className?: string;
    style?: React.CSSProperties;
  }>
> = {
  BookOpen,
  Film,
  Tv,
  Podcast,
  Disc3,
  Music,
  Youtube,
  FileText,
  Ticket,
  MoreHorizontal,
};

const NOTE_PLACEHOLDERS: Record<string, string> = {
  book: "What's the one idea you'll remember?",
  film: "How did it make you feel?",
  podcast: "What surprised you?",
  album: "When/where did you listen?",
  song: "When/where did you listen?",
  youtube: "Why was this worth watching?",
  tv_series: "How did it make you feel?",
  tv_episode: "How did it make you feel?",
  article: "What's the key takeaway?",
  live_event: "What was the highlight?",
  other: "What will you want to remember?",
};

interface EntryDetailProps {
  entry: Entry;
  onClose: () => void;
  onUpdate: (entry: Entry) => void;
  onDelete: (id: string) => void;
}

export function EntryDetail({
  entry,
  onClose,
  onUpdate,
  onDelete,
}: EntryDetailProps) {
  const [note, setNote] = useState(entry.note ?? "");
  const [rating, setRating] = useState<number | null>(entry.rating);
  const [saving, setSaving] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const config = MEDIA_TYPE_CONFIG[entry.media_type];
  const Icon = ICON_MAP[config.icon];
  const isPortrait =
    entry.media_type === "book" || entry.media_type === "film";

  const hasChanges =
    note !== (entry.note ?? "") || rating !== entry.rating;

  const handleSave = async () => {
    if (!hasChanges || saving) return;
    setSaving(true);

    try {
      const res = await fetch(`/api/entries/${entry.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          note: note.trim() || null,
          rating: rating,
        }),
      });

      if (res.ok) {
        const updated = await res.json();
        toast.success("Saved!");
        onUpdate(updated);
      }
    } catch {
      toast.error("Failed to save.");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    setDeleting(true);
    try {
      const res = await fetch(`/api/entries/${entry.id}`, {
        method: "DELETE",
      });

      if (res.ok) {
        toast.success("Entry deleted.");
        onDelete(entry.id);
        onClose();
      }
    } catch {
      toast.error("Failed to delete.");
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-[100] flex items-end md:items-center justify-center animate-fade-in"
      onClick={onClose}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />

      {/* Modal */}
      <div
        className="relative w-full max-w-lg bg-background-card rounded-t-2xl md:rounded-2xl border border-border shadow-2xl max-h-[90vh] overflow-y-auto animate-slide-up md:animate-scale-in"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 z-10 p-1.5 rounded-lg bg-background-elevated/80 text-foreground-muted hover:text-foreground transition-colors"
        >
          <X size={18} />
        </button>

        {/* Thumbnail */}
        <div className="relative flex items-center justify-center pt-6 px-6">
          {entry.thumbnail_url ? (
            <Image
              src={entry.thumbnail_url}
              alt={entry.title}
              width={isPortrait ? 160 : 240}
              height={isPortrait ? 240 : 160}
              className="rounded-xl object-cover shadow-lg"
              style={{
                width: isPortrait ? 160 : 240,
                height: isPortrait ? 240 : 160,
              }}
            />
          ) : (
            <div
              className="flex items-center justify-center rounded-xl"
              style={{
                width: isPortrait ? 160 : 240,
                height: isPortrait ? 240 : 160,
                backgroundColor: `${config.color}20`,
              }}
            >
              {Icon && (
                <Icon size={48} className="opacity-50" style={{ color: config.color }} />
              )}
            </div>
          )}
        </div>

        {/* Content */}
        <div className="p-6 space-y-4">
          {/* Title & info */}
          <div className="text-center">
            <h2 className="text-xl font-serif font-semibold leading-tight">
              {entry.title}
            </h2>
            {(entry.author_or_creator || entry.year) && (
              <p className="text-sm text-foreground-muted mt-1">
                {entry.author_or_creator}
                {entry.author_or_creator && entry.year && " \u00B7 "}
                {entry.year}
              </p>
            )}
            <div className="flex items-center justify-center gap-2 mt-2">
              <MediaTypeBadge type={entry.media_type} />
            </div>
          </div>

          {/* Date logged */}
          <div className="flex items-center justify-center gap-2 text-xs text-foreground-subtle">
            <Calendar size={12} />
            <span>
              Logged {format(parseISO(entry.logged_at), "MMMM d, yyyy 'at' h:mm a")}
            </span>
          </div>

          {/* Rating */}
          <div>
            <label className="block text-sm text-foreground-muted mb-1.5">
              Rating
            </label>
            <StarRating rating={rating} onRate={setRating} size={28} />
          </div>

          {/* Note */}
          <div>
            <label className="block text-sm text-foreground-muted mb-1.5">
              Note
            </label>
            <div className="relative">
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value.slice(0, 280))}
                placeholder={
                  NOTE_PLACEHOLDERS[entry.media_type] ||
                  NOTE_PLACEHOLDERS.other
                }
                rows={3}
                className="w-full resize-none rounded-lg bg-background-elevated p-3 text-sm text-foreground placeholder:text-foreground-subtle"
              />
              <span className="absolute bottom-2 right-2 text-xs text-foreground-subtle">
                {note.length}/280
              </span>
            </div>
          </div>

          {/* Save button */}
          {hasChanges && (
            <button
              onClick={handleSave}
              disabled={saving}
              className="w-full rounded-lg bg-primary px-4 py-2.5 font-medium text-white transition-colors hover:bg-primary-hover disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save changes"}
            </button>
          )}

          {/* Source link */}
          {entry.source_url && (
            <a
              href={entry.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-center gap-2 text-sm text-primary hover:text-primary-hover transition-colors"
            >
              <ExternalLink size={14} />
              View source
            </a>
          )}

          {/* Delete */}
          <div className="pt-2 border-t border-border">
            {!confirmDelete ? (
              <button
                onClick={() => setConfirmDelete(true)}
                className="flex items-center gap-2 text-sm text-foreground-subtle hover:text-red-400 transition-colors"
              >
                <Trash2 size={14} />
                Delete entry
              </button>
            ) : (
              <div className="flex items-center gap-3">
                <p className="text-sm text-red-400 flex-1">
                  Delete this entry?
                </p>
                <button
                  onClick={handleDelete}
                  disabled={deleting}
                  className="rounded-lg bg-red-500/20 px-3 py-1.5 text-sm font-medium text-red-400 hover:bg-red-500/30 transition-colors disabled:opacity-50"
                >
                  {deleting ? "Deleting..." : "Yes, delete"}
                </button>
                <button
                  onClick={() => setConfirmDelete(false)}
                  className="rounded-lg px-3 py-1.5 text-sm text-foreground-muted hover:text-foreground transition-colors"
                >
                  Cancel
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
