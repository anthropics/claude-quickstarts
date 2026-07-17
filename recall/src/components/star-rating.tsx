"use client";

import { Star } from "lucide-react";

export function StarRating({
  rating,
  onRate,
  size = 16,
}: {
  rating: number | null;
  onRate?: (rating: number) => void;
  size?: number;
}) {
  return (
    <div className="inline-flex gap-0.5">
      {[1, 2, 3, 4, 5].map((star) => (
        <button
          key={star}
          type="button"
          onClick={() => onRate?.(star === rating ? 0 : star)}
          disabled={!onRate}
          className={`transition-colors ${onRate ? "cursor-pointer hover:text-amber-400" : "cursor-default"}`}
        >
          <Star
            size={size}
            className={
              rating && star <= rating
                ? "fill-amber-400 text-amber-400"
                : "text-foreground-subtle"
            }
          />
        </button>
      ))}
    </div>
  );
}
