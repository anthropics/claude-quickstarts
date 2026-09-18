import Anthropic from "@anthropic-ai/sdk";
import { buildSystemPrompt } from "@/lib/system-prompt";
import { ChatMessage, WeddingParams } from "@/types/wedding";

export const runtime = "nodejs";

const client = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY,
});

const MODEL = process.env.ANTHROPIC_MODEL || "claude-sonnet-5";

export async function POST(req: Request) {
  const { messages, params } = (await req.json()) as {
    messages: ChatMessage[];
    params: WeddingParams;
  };

  if (!process.env.ANTHROPIC_API_KEY) {
    return new Response(
      "Chybí ANTHROPIC_API_KEY. Nastavte jej v souboru .env.local a restartujte server.",
      { status: 500 },
    );
  }

  const systemPrompt = buildSystemPrompt(params);

  const stream = new ReadableStream({
    async start(controller) {
      const encoder = new TextEncoder();
      try {
        const anthropicStream = client.messages.stream({
          model: MODEL,
          max_tokens: 4096,
          system: systemPrompt,
          messages: messages.map((m) => ({ role: m.role, content: m.content })),
        });

        anthropicStream.on("text", (text) => {
          controller.enqueue(encoder.encode(text));
        });

        await anthropicStream.finalMessage();
        controller.close();
      } catch (error) {
        console.error("Chyba při komunikaci s Claude API:", error);
        controller.enqueue(
          encoder.encode(
            "\n\n_Omlouváme se, došlo k technické chybě při generování odpovědi. Zkuste to prosím znovu._",
          ),
        );
        controller.close();
      }
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
    },
  });
}
