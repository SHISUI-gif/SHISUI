export type ChatRole = "user" | "assistant";

export interface ChatMessage {
  role: ChatRole;
  content: string;
  thinking?: string;
}

export type ChatStreamEvent =
  | { type: "thinking"; text: string }
  | { type: "content"; text: string }
  | { type: "tool_status"; text: string };
