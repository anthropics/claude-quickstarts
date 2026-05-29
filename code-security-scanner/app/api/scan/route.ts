import { NextRequest } from "next/server";
import Anthropic from "@anthropic-ai/sdk";

const anthropic = new Anthropic({
    apiKey: process.env.ANTHROPIC_API_KEY!,
});

export const runtime = "edge";

const SYSTEM_PROMPT = `You are an expert code security auditor. Your task is to analyze code snippets for security vulnerabilities.

When given a code snippet, you MUST respond ONLY with valid JSON (no markdown, no backticks, no explanation outside the JSON). Use this exact format:

{
  "vulnerabilities": [
    {
      "name": "Vulnerability Name (e.g. SQL Injection, XSS, Command Injection)",
      "severity": "Critical" | "High" | "Medium" | "Low",
      "line": <line number as integer, or null if not applicable>,
      "description": "Clear explanation of the vulnerability and why it's dangerous",
      "fix": "Specific code fix or recommendation to remediate the issue"
    }
  ],
  "summary": "A brief overall security assessment of the code (1-2 sentences)"
}

Severity guidelines:
- Critical: Remote code execution, SQL injection with data exfiltration, authentication bypass, unsanitized command execution
- High: XSS, CSRF, path traversal, insecure deserialization, hardcoded secrets
- Medium: Information disclosure, missing input validation, weak cryptography, insecure defaults
- Low: Missing security headers, verbose error messages, deprecated functions, minor best-practice violations

Rules:
1. Be thorough — check for ALL categories of vulnerabilities
2. Be precise with line numbers when possible
3. If the code is secure, return an empty vulnerabilities array with a positive summary
4. Fix recommendations should be specific and actionable, ideally with corrected code snippets
5. Do NOT wrap your response in markdown code blocks — respond with raw JSON only`;

export async function POST(req: NextRequest) {
    try {
        const { code, language } = await req.json();

        if (!code || typeof code !== "string" || code.trim().length === 0) {
            return new Response(
                JSON.stringify({ error: "Code snippet is required" }),
                { status: 400, headers: { "Content-Type": "application/json" } }
            );
        }

        const response = await anthropic.messages.create({
            model: "claude-sonnet-4-20250514",
            max_tokens: 4096,
            temperature: 0,
            system: SYSTEM_PROMPT,
            messages: [
                {
                    role: "user",
                    content: `Analyze the following ${language || "code"} snippet for security vulnerabilities:\n\n${code}`,
                },
            ],
        });

        const textContent = response.content.find((c) => c.type === "text");
        if (!textContent || textContent.type !== "text") {
            return new Response(
                JSON.stringify({ error: "No response from Claude" }),
                { status: 500, headers: { "Content-Type": "application/json" } }
            );
        }

        // Parse the JSON response from Claude
        let scanResult;
        try {
            // Strip any accidental markdown code fences
            let raw = textContent.text.trim();
            if (raw.startsWith("```")) {
                raw = raw.replace(/^```(?:json)?\n?/, "").replace(/\n?```$/, "");
            }
            scanResult = JSON.parse(raw);
        } catch {
            return new Response(
                JSON.stringify({
                    error: "Failed to parse analysis results",
                    raw: textContent.text,
                }),
                { status: 500, headers: { "Content-Type": "application/json" } }
            );
        }

        // Validate structure
        if (!scanResult.vulnerabilities || !Array.isArray(scanResult.vulnerabilities)) {
            scanResult = {
                vulnerabilities: [],
                summary: scanResult.summary || "Analysis completed but no structured results were returned.",
            };
        }

        return new Response(JSON.stringify(scanResult), {
            headers: {
                "Content-Type": "application/json",
                "Cache-Control": "no-cache",
            },
        });
    } catch (error) {
        console.error("Scan API Error:", error);

        if (error instanceof Anthropic.APIError) {
            return new Response(
                JSON.stringify({
                    error: "API Error",
                    details: error.message,
                    code: error.status,
                }),
                { status: error.status, headers: { "Content-Type": "application/json" } }
            );
        }

        return new Response(
            JSON.stringify({
                error: error instanceof Error ? error.message : "An unknown error occurred",
            }),
            {
                status: 500,
                headers: { "Content-Type": "application/json" },
            }
        );
    }
}
