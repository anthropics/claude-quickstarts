export interface WeddingParams {
  date: string;
  venue: string;
  budget: string;
  guestCount: string;
  style: string;
  priorities: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}
