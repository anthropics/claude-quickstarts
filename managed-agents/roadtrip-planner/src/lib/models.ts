/**
 * Models the header picker offers, and the only values /api/session accepts
 * as a `model` override. The list is shared so the server never runs the
 * stored agent on a model the UI did not offer.
 */
export const MODELS = ["claude-sonnet-5", "claude-opus-5", "claude-haiku-4-5"] as const;
