"use client";

import { ChevronDown } from "lucide-react";

const LANGUAGES = [
    "Python",
    "JavaScript",
    "TypeScript",
    "C++",
    "C",
    "Java",
    "Go",
    "Rust",
    "PHP",
    "Ruby",
    "C#",
    "Swift",
    "Kotlin",
    "Solidity",
    "SQL",
    "Shell",
    "Other",
] as const;

interface CodeInputProps {
    code: string;
    language: string;
    onCodeChange: (code: string) => void;
    onLanguageChange: (language: string) => void;
    disabled?: boolean;
}

export function CodeInput({
    code,
    language,
    onCodeChange,
    onLanguageChange,
    disabled = false,
}: CodeInputProps) {
    const lineCount = code.split("\n").length;

    return (
        <div className="flex flex-col overflow-hidden rounded-xl border border-border/60 bg-card shadow-xl shadow-black/5">
            {/* Toolbar */}
            <div className="flex items-center justify-between border-b border-border/40 bg-muted/30 px-4 py-2.5">
                <div className="flex items-center gap-2">
                    <div className="flex gap-1.5">
                        <span className="h-3 w-3 rounded-full bg-red-500/70" />
                        <span className="h-3 w-3 rounded-full bg-yellow-500/70" />
                        <span className="h-3 w-3 rounded-full bg-green-500/70" />
                    </div>
                    <span className="ml-2 text-xs text-muted-foreground">
                        Paste your code below
                    </span>
                </div>
                <div className="relative">
                    <select
                        value={language}
                        onChange={(e) => onLanguageChange(e.target.value)}
                        disabled={disabled}
                        className="appearance-none rounded-md border border-border/60 bg-background px-3 py-1 pr-7 text-xs font-medium text-foreground transition-colors hover:border-border focus:outline-none focus:ring-2 focus:ring-ring/20 disabled:opacity-50"
                    >
                        {LANGUAGES.map((lang) => (
                            <option key={lang} value={lang}>
                                {lang}
                            </option>
                        ))}
                    </select>
                    <ChevronDown className="pointer-events-none absolute right-1.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                </div>
            </div>

            {/* Editor area */}
            <div className="relative flex min-h-[320px]">
                {/* Line numbers */}
                <div className="select-none border-r border-border/30 bg-muted/20 px-3 py-4 text-right font-mono text-xs leading-6 text-muted-foreground/50">
                    {Array.from({ length: Math.max(lineCount, 15) }, (_, i) => (
                        <div key={i + 1}>{i + 1}</div>
                    ))}
                </div>

                {/* Code textarea */}
                <textarea
                    id="code-input"
                    value={code}
                    onChange={(e) => onCodeChange(e.target.value)}
                    disabled={disabled}
                    spellCheck={false}
                    autoComplete="off"
                    placeholder={`// Paste your ${language} code here...\n// Example:\nimport os\nuser_input = input("Enter command: ")\nos.system(user_input)  # Command injection vulnerability`}
                    className="code-editor scrollbar-thin w-full resize-none bg-transparent px-4 py-4 text-sm leading-6 text-foreground placeholder:text-muted-foreground/30 focus:outline-none disabled:opacity-50"
                />
            </div>

            {/* Status bar */}
            <div className="flex items-center justify-between border-t border-border/30 bg-muted/20 px-4 py-1.5">
                <span className="text-[10px] text-muted-foreground/60">
                    {lineCount} {lineCount === 1 ? "line" : "lines"} · {code.length}{" "}
                    characters
                </span>
                <span className="text-[10px] text-muted-foreground/60">
                    {language}
                </span>
            </div>
        </div>
    );
}
