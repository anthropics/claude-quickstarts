"use client";

import { useState } from "react";
import { Header } from "@/components/header";
import { CodeInput } from "@/components/code-input";
import { ScanResults } from "@/components/scan-results";
import { LoadingSkeleton } from "@/components/loading-skeleton";
import type { ScanResult } from "@/types/scan";
import { Scan, Sparkles, Code2, ShieldCheck, Zap } from "lucide-react";

export default function Home() {
    const [code, setCode] = useState("");
    const [language, setLanguage] = useState("Python");
    const [result, setResult] = useState<ScanResult | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleScan = async () => {
        if (!code.trim()) return;

        setLoading(true);
        setError(null);
        setResult(null);

        try {
            const res = await fetch("/api/scan", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ code, language }),
            });

            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                throw new Error(
                    errData.details || errData.error || `Scan failed (${res.status})`
                );
            }

            const data: ScanResult = await res.json();
            setResult(data);
        } catch (err) {
            setError(
                err instanceof Error ? err.message : "An unexpected error occurred"
            );
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex min-h-screen flex-col">
            <Header />

            <main className="flex-1">
                <div className="mx-auto max-w-7xl px-6 py-8">
                    {/* Hero */}
                    <div className="mb-8 text-center">
                        <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-border/40 bg-muted/30 px-3 py-1 text-xs text-muted-foreground">
                            <Sparkles className="h-3 w-3 text-indigo-400" />
                            AI-powered security analysis
                        </div>
                        <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
                            Scan your code for{" "}
                            <span className="bg-gradient-to-r from-indigo-400 via-purple-400 to-cyan-400 bg-clip-text text-transparent">
                                vulnerabilities
                            </span>
                        </h2>
                        <p className="mt-2 text-muted-foreground">
                            Paste any code snippet — Python, JavaScript, C++, and more — and
                            get an instant security report.
                        </p>
                    </div>

                    <div className="grid gap-8 lg:grid-cols-2">
                        {/* Left column: input */}
                        <div className="space-y-4">
                            <CodeInput
                                code={code}
                                language={language}
                                onCodeChange={setCode}
                                onLanguageChange={setLanguage}
                                disabled={loading}
                            />

                            {/* Scan button */}
                            <button
                                id="scan-button"
                                onClick={handleScan}
                                disabled={loading || !code.trim()}
                                className="group relative flex w-full items-center justify-center gap-2 overflow-hidden rounded-xl bg-gradient-to-r from-indigo-600 to-cyan-600 px-6 py-3.5 text-sm font-semibold text-white shadow-lg shadow-indigo-500/25 transition-all hover:shadow-xl hover:shadow-indigo-500/30 disabled:cursor-not-allowed disabled:opacity-50 disabled:shadow-none"
                            >
                                <div className="absolute inset-0 bg-gradient-to-r from-indigo-500 to-cyan-500 opacity-0 transition-opacity group-hover:opacity-100" />
                                <span className="relative flex items-center gap-2">
                                    {loading ? (
                                        <>
                                            <div className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                                            Analyzing with Claude...
                                        </>
                                    ) : (
                                        <>
                                            <Scan className="h-4 w-4" />
                                            Scan for Vulnerabilities
                                        </>
                                    )}
                                </span>
                            </button>

                            {/* Error */}
                            {error && (
                                <div className="animate-fade-in-up rounded-xl border border-red-500/30 bg-red-500/5 p-4">
                                    <p className="text-sm text-red-400">{error}</p>
                                </div>
                            )}

                            {/* Feature cards (only when no results) */}
                            {!result && !loading && (
                                <div className="grid grid-cols-3 gap-3 pt-2">
                                    {[
                                        {
                                            icon: Code2,
                                            title: "Multi-Language",
                                            desc: "Python, JS, C++, and more",
                                        },
                                        {
                                            icon: ShieldCheck,
                                            title: "Deep Analysis",
                                            desc: "OWASP Top 10 coverage",
                                        },
                                        {
                                            icon: Zap,
                                            title: "Instant Fixes",
                                            desc: "Actionable recommendations",
                                        },
                                    ].map((feat) => (
                                        <div
                                            key={feat.title}
                                            className="rounded-lg border border-border/30 bg-card/50 p-3 text-center"
                                        >
                                            <feat.icon className="mx-auto mb-1.5 h-4 w-4 text-indigo-400" />
                                            <p className="text-xs font-medium text-foreground">
                                                {feat.title}
                                            </p>
                                            <p className="mt-0.5 text-[10px] text-muted-foreground">
                                                {feat.desc}
                                            </p>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>

                        {/* Right column: results */}
                        <div>
                            {loading && <LoadingSkeleton />}
                            {result && !loading && <ScanResults result={result} />}
                            {!result && !loading && (
                                <div className="flex h-full flex-col items-center justify-center rounded-xl border border-dashed border-border/40 bg-card/30 p-12 text-center">
                                    <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-muted/50">
                                        <ShieldCheck className="h-8 w-8 text-muted-foreground/40" />
                                    </div>
                                    <h3 className="text-sm font-medium text-muted-foreground">
                                        Security Report
                                    </h3>
                                    <p className="mt-1 text-xs text-muted-foreground/60">
                                        Paste code and click scan to see results here
                                    </p>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </main>

            {/* Footer */}
            <footer className="border-t border-border/30 py-4">
                <div className="mx-auto max-w-7xl px-6">
                    <p className="text-center text-xs text-muted-foreground/50">
                        Built with Claude AI by Anthropic · This tool provides automated
                        security suggestions and should not replace a professional security
                        audit.
                    </p>
                </div>
            </footer>
        </div>
    );
}
