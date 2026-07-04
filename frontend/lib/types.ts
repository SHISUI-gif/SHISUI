export type ChatRole = "user" | "assistant";

export interface ChatMessage {
  role: ChatRole;
  content: string;
  thinking?: string;
  /** クライアント側のみで使う、ストリーミング中の吹き出しを一意に識別するID
   * (複数のメッセージを同時に送信中でも、どの吹き出しを更新すべきか分かるようにする)。
   * バックエンドとの送受信には使わない。 */
  _localId?: number;
  /** この吹き出し固有のツール実行ステータス(例: 「検索中...」)。クライアント側のみ。 */
  _toolStatus?: string;
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

export interface AvatarItem {
  slug: string;
  display_name: string;
  asset: string;
}

export interface ActivityEntry {
  timestamp: string;
  kind: "sleep" | "study" | "debate";
  summary: string;
  details: Record<string, unknown>;
}
