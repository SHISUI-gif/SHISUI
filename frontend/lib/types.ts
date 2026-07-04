export type ChatRole = "user" | "assistant";

export interface ChatMessage {
  role: ChatRole;
  content: string;
  thinking?: string;
}

export type ChatStreamEvent =
  | { type: "thinking"; text: string; conversation_id: number }
  | { type: "content"; text: string; conversation_id: number }
  | { type: "tool_status"; text: string; conversation_id: number };

export interface AuthUser {
  token: string;
  userId: number;
  name: string;
}

export interface Conversation {
  id: number;
  title: string;
  created_at: string;
  updated_at: string;
}
