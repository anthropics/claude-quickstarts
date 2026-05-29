"use client";

import { SeverityBadge } from "./severity-badge";
import type { ScanResult, Severity } from "@/types/scan";
import {
    ShieldCheck,
    ShieldAlert,
    AlertTriangle,
    MapPin,
    Wrench,
    FileWarning,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface ScanResultsProps {
    result: ScanResult;
}

const severityOrder: Record<Severity, number> = {
    Critical: 0,
    High: 1,
    Medium: 2,
    Low: 3,
};

const severityIcons: Record<Severity, typeof ShieldAlert> = {
    Critical: ShieldAlert,
    High: AlertTriangle,
    Medium: FileWarning,
    Low: ShieldCheck,
};

const severityBorderColors: Record<Severity, string> = {
    Critical: "border-l-red-500",
    High: "border-l-orange-500",
    Medium: "border-l-yellow-500",
    Low: "border-l-blue-500",
};

export function ScanResults({ result }: ScanResultsProps) {
    const { vulnerabilities, summary } = result;
    const sorted = [...vulnerabilities].sort(
        (a, b) => severityOrder[a.severity] - severityOrder[b.severity]
    );

    const counts = vulnerabilities.reduce(
        (acc, v) => {
            acc[v.severity] = (acc[v.severity] || 0) + 1;
            return acc;
        },
        {} as Record<Severity, number>
    );

    const isClean = vulnerabilities.length === 0;

    return (
        <div className="space-y-4 animate-fade-in-up">
            {/* Summary */}
            <div
                className={cn(
                    "overflow-hidden rounded-xl border p-5",
                    isClean
                        ? "border-emerald-500/30 bg-emerald-500/5"
                        : "border-amber-500/30 bg-amber-500/5"
                )}
            >
                <div className="flex items-start gap-3">
                    {isClean ? (
                        <ShieldCheck className="mt-0.5 h-5 w-5 flex-shrink-0 text-emerald-400" />
                    ) : (
                        <ShieldAlert className="mt-0.5 h-5 w-5 flex-shrink-0 text-amber-400" />
                    )}
                    <div>
                        <h3
                            className={cn(
                                "text-sm font-semibold",
                                isClean ? "text-emerald-400" : "text-amber-400"
                            )}
                        >
                            {isClean ? "No Vulnerabilities Detected" : "Security Issues Found"}
                        </h3>
                        <p className="mt-1 text-sm text-muted-foreground">{summary}</p>
                    </div>
                </div>
            </div>

            {/* Stats bar */}
            {!isClean && (
                <div className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-lg border border-border/30 bg-card/50 px-4 py-3">
                    <span className="text-xs font-medium text-muted-foreground">
                        {vulnerabilities.length}{" "}
                        {vulnerabilities.length === 1 ? "issue" : "issues"} found
                    </span>
                    <div className="h-4 w-px bg-border/50" />
                    {(["Critical", "High", "Medium", "Low"] as Severity[]).map(
                        (sev) =>
                            counts[sev] && (
                                <div key={sev} className="flex items-center gap-1.5">
                                    <SeverityBadge severity={sev} />
                                    <span className="text-xs text-muted-foreground">
                                        × {counts[sev]}
                                    </span>
                                </div>
                            )
                    )}
                </div>
            )}

            {/* Vulnerability cards */}
            {sorted.map((vuln, idx) => {
                const Icon = severityIcons[vuln.severity];
                return (
                    <div
                        key={idx}
                        className={cn(
                            "animate-fade-in-up overflow-hidden rounded-xl border border-border/40 border-l-[3px] bg-card transition-all hover:border-border/60 hover:shadow-lg hover:shadow-black/5",
                            severityBorderColors[vuln.severity]
                        )}
                        style={{ animationDelay: `${idx * 80}ms` }}
                    >
                        <div className="p-5">
                            {/* Header */}
                            <div className="flex items-start justify-between gap-3">
                                <div className="flex items-start gap-3">
                                    <Icon className="mt-0.5 h-4 w-4 flex-shrink-0 text-muted-foreground" />
                                    <div>
                                        <h4 className="text-sm font-semibold text-foreground">
                                            {vuln.name}
                                        </h4>
                                        {vuln.line !== null && (
                                            <div className="mt-1 flex items-center gap-1 text-xs text-muted-foreground">
                                                <MapPin className="h-3 w-3" />
                                                Line {vuln.line}
                                            </div>
                                        )}
                                    </div>
                                </div>
                                <SeverityBadge severity={vuln.severity} />
                            </div>

                            {/* Description */}
                            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                                {vuln.description}
                            </p>

                            {/* Fix recommendation */}
                            <div className="mt-4 rounded-lg bg-muted/30 p-3.5 ring-1 ring-inset ring-border/30">
                                <div className="flex items-center gap-1.5 text-xs font-medium text-foreground">
                                    <Wrench className="h-3.5 w-3.5 text-indigo-400" />
                                    Fix Recommendation
                                </div>
                                <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
                                    {vuln.fix}
                                </p>
                            </div>
                        </div>
                    </div>
                );
            })}
        </div>
    );
}
