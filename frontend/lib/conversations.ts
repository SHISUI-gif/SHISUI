import { AuthError } from "./api"
import type { ChatMessage, Conversation } from "./types"

function authHeaders(token: string): HeadersInit {
  return { Authorization: `Bearer ${token}` }
}

export async function listConversations(token: string): Promise<Conversation[]> {
  const response = await fetch("/api/conversations", { headers: authHeaders(token) })
  if (response.status === 401) {
    throw new AuthError("セッションが切れました。もう一度ログインしてください。")
  }
  if (!response.ok) return []
  return response.json()
}

export async function getConversationMessages(
  token: string,
  conversationId: number,
): Promise<ChatMessage[]> {
  const response = await fetch(`/api/conversations/${conversationId}/messages`, {
    headers: authHeaders(token),
  })
  if (response.status === 401) {
    throw new AuthError("セッションが切れました。もう一度ログインしてください。")
  }
  if (!response.ok) return []
  return response.json()
}
