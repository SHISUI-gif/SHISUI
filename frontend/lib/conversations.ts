import type { ChatMessage, Conversation } from "./types"

function authHeaders(token: string): HeadersInit {
  return { Authorization: `Bearer ${token}` }
}

export async function listConversations(token: string): Promise<Conversation[]> {
  const response = await fetch("/api/conversations", { headers: authHeaders(token) })
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
  if (!response.ok) return []
  return response.json()
}
