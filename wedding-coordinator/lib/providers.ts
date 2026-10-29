export type Provider = "anthropic" | "gemini";

// AI_PROVIDER picks explicitly; otherwise we prefer Anthropic when both keys
// are set, and fall back to whichever key is actually present.
export function resolveProvider(): Provider | null {
  const requested = process.env.AI_PROVIDER?.toLowerCase();
  if (requested === "anthropic" || requested === "gemini") return requested;

  if (process.env.ANTHROPIC_API_KEY) return "anthropic";
  if (process.env.GEMINI_API_KEY) return "gemini";
  return null;
}
