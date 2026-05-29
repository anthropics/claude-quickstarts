"use client";

export function LoadingSkeleton() {
    return (
        <div className="space-y-4">
            {/* Summary skeleton */}
            <div className="overflow-hidden rounded-xl border border-border/40 bg-card p-5">
                <div className="flex items-center gap-3 mb-4">
                    <div className="h-5 w-5 rounded animate-shimmer" />
                    <div className="h-5 w-32 rounded animate-shimmer" />
                </div>
                <div className="space-y-2">
                    <div className="h-4 w-full rounded animate-shimmer" />
                    <div className="h-4 w-3/4 rounded animate-shimmer" />
                </div>
            </div>

            {/* Stats bar skeleton */}
            <div className="flex items-center gap-3 rounded-lg border border-border/30 bg-card/50 px-4 py-3">
                {[1, 2, 3, 4].map((i) => (
                    <div key={i} className="flex items-center gap-2">
                        <div className="h-4 w-4 rounded animate-shimmer" />
                        <div className="h-4 w-12 rounded animate-shimmer" />
                    </div>
                ))}
            </div>

            {/* Vulnerability card skeletons */}
            {[1, 2, 3].map((i) => (
                <div
                    key={i}
                    className="overflow-hidden rounded-xl border border-border/40 bg-card p-5"
                    style={{ animationDelay: `${i * 150}ms` }}
                >
                    <div className="flex items-start justify-between mb-3">
                        <div className="space-y-2">
                            <div className="h-5 w-48 rounded animate-shimmer" />
                            <div className="h-3 w-24 rounded animate-shimmer" />
                        </div>
                        <div className="h-6 w-16 rounded-full animate-shimmer" />
                    </div>
                    <div className="space-y-2 mt-4">
                        <div className="h-4 w-full rounded animate-shimmer" />
                        <div className="h-4 w-5/6 rounded animate-shimmer" />
                    </div>
                    <div className="mt-4 rounded-lg bg-muted/30 p-3 space-y-2">
                        <div className="h-4 w-20 rounded animate-shimmer" />
                        <div className="h-4 w-full rounded animate-shimmer" />
                        <div className="h-4 w-2/3 rounded animate-shimmer" />
                    </div>
                </div>
            ))}
        </div>
    );
}
