"use client";

import { Shield, ShieldAlert } from "lucide-react";

export function Header() {
    return (
        <header className="border-b border-border/40 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
            <div className="mx-auto flex h-16 max-w-7xl items-center gap-3 px-6">
                <div className="relative flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-cyan-400 shadow-lg shadow-indigo-500/25">
                    <Shield className="h-5 w-5 text-white" />
                    <ShieldAlert className="absolute -right-1 -top-1 h-3.5 w-3.5 text-amber-400 drop-shadow-md" />
                </div>
                <div>
                    <h1 className="text-lg font-semibold tracking-tight">
                        Code Security Scanner
                    </h1>
                    <p className="text-xs text-muted-foreground">
                        Powered by Claude AI
                    </p>
                </div>
                <div className="ml-auto flex items-center gap-2">
                    <span className="inline-flex items-center rounded-full bg-indigo-500/10 px-2.5 py-0.5 text-xs font-medium text-indigo-400 ring-1 ring-inset ring-indigo-500/20">
                        claude-sonnet-4-20250514
                    </span>
                </div>
            </div>
        </header>
    );
}
