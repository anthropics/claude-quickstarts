import { TEMPLATE_TYPES } from "@/app/letters/_lib/data";

export interface TemplateData {
  name: string;
  type: string;
  body_template: string;
}

/** Validates a letter-template create/update payload. */
export function validateTemplatePayload(body: unknown): { data: TemplateData } | { error: string } {
  if (typeof body !== "object" || body === null || Array.isArray(body)) {
    return { error: "Request body must be a JSON object." };
  }
  const input = body as Record<string, unknown>;

  const name = typeof input.name === "string" ? input.name.trim() : "";
  if (!name) return { error: "name is required." };
  if (name.length > 120) return { error: "name must be 120 characters or fewer." };

  const type = typeof input.type === "string" ? input.type : "";
  if (!(TEMPLATE_TYPES as readonly string[]).includes(type)) {
    return { error: `type must be one of: ${TEMPLATE_TYPES.join(", ")}.` };
  }

  const bodyTemplate = typeof input.body_template === "string" ? input.body_template : "";
  if (!bodyTemplate.trim()) return { error: "body_template is required." };

  return { data: { name, type, body_template: bodyTemplate } };
}
