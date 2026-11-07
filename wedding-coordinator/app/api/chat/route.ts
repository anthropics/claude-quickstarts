import Anthropic from "@anthropic-ai/sdk";
import { GoogleGenerativeAI } from "@google/generative-ai";
import { buildSystemPrompt } from "@/lib/system-prompt";
import { resolveProvider } from "@/lib/providers";
import { ChatMessage, WeddingParams } from "@/types/wedding";

export const runtime = "nodejs";

const client = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY,
});

const ANTHROPIC_MODEL = process.env.ANTHROPIC_MODEL || "claude-sonnet-5";
// Override with whichever current Gemini model your API key has access to;
// see https://ai.google.dev/gemini-api/docs/models for the latest names.
const GEMINI_MODEL = process.env.GEMINI_MODEL || "gemini-2.5-flash";

async function streamFromAnthropic(
  controller: ReadableStreamDefaultController,
  encoder: TextEncoder,
  systemPrompt: string,
  messages: ChatMessage[],
) {
  const anthropicStream = client.messages.stream({
    model: ANTHROPIC_MODEL,
    max_tokens: 4096,
    system: systemPrompt,
    messages: messages.map((m) => ({ role: m.role, content: m.content })),
  });

  anthropicStream.on("text", (text) => {
    controller.enqueue(encoder.encode(text));
  });

  await anthropicStream.finalMessage();
}

async function streamFromGemini(
  controller: ReadableStreamDefaultController,
  encoder: TextEncoder,
  systemPrompt: string,
  messages: ChatMessage[],
) {
  const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY!);
  const model = genAI.getGenerativeModel({
    model: GEMINI_MODEL,
    systemInstruction: systemPrompt,
  });

  const result = await model.generateContentStream({
    contents: messages.map((m) => ({
      role: m.role === "assistant" ? "model" : "user",
      parts: [{ text: m.content }],
    })),
  });

  for await (const chunk of result.stream) {
    controller.enqueue(encoder.encode(chunk.text()));
  }
}

export async function POST(req: Request) {
  const { messages, params } = (await req.json()) as {
    messages: ChatMessage[];
    params: WeddingParams;
  };

  const provider = resolveProvider();

  if (!provider) {
    return new Response(
      "Chybí API klíč. Nastavte ANTHROPIC_API_KEY nebo GEMINI_API_KEY v souboru .env.local a restartujte server.",
      { status: 500 },
    );
  }

  const systemPrompt = buildSystemPrompt(params);

  const stream = new ReadableStream({
    async start(controller) {
      const encoder = new TextEncoder();
      try {
        if (provider === "anthropic") {
          await streamFromAnthropic(controller, encoder, systemPrompt, messages);
        } else {
          await streamFromGemini(controller, encoder, systemPrompt, messages);
        }
        controller.close();
      } catch (error) {
        console.error(`Chyba při komunikaci s ${provider} API:`, error);
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
