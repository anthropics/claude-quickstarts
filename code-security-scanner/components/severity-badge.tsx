"use client";

import { cn } from "@/lib/utils";
import type { Severity } from "@/types/scan";

const severityConfig: Record<
    Severity,
    { bg: string; text: string; ring: string; dot: string }
> = {
    Critical: {
        bg: "bg-red-500/10",
        text: "text-red-400",
        ring: "ring-red-500/30",
        dot: "bg-red-500",
    },
    High: {
        bg: "bg-orange-500/10",
        text: "text-orange-400",
        ring: "ring-orange-500/30",
        dot: "bg-orange-500",
    },
    Medium: {
        bg: "bg-yellow-500/10",
        text: "text-yellow-400",
        ring: "ring-yellow-500/30",
        dot: "bg-yellow-500",
    },
    Low: {
        bg: "bg-blue-500/10",
        text: "text-blue-400",
        ring: "ring-blue-500/30",
        dot: "bg-blue-500",
    },
};

interface SeverityBadgeProps {
    severity: Severity;
    className?: string;
}

export function SeverityBadge({ severity, className }: SeverityBadgeProps) {
    const config = severityConfig[severity];

    return (
        <span
            className={cn(
                "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset",
                config.bg,
                config.text,
                config.ring,
                className
            )}
        >
            <span className={cn("h-1.5 w-1.5 rounded-full", config.dot)} />
            {severity}
        </span>
    );
}
