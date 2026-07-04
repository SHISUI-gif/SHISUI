import { AuthError } from "./api"
import type { UserFeedbackEntry } from "./types"

export async function submitFeedback(token: string, content: string): Promise<void> {
  const response = await fetch("/api/feedback", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ content }),
  })
  if (response.status === 401) {
    throw new AuthError("セッションが切れました。もう一度ログインしてください。")
  }
  if (!response.ok) {
    const body = await response.json()
    throw new Error(body.detail || "送信に失敗しました。")
  }
}

export async function getAllFeedback(token: string): Promise<UserFeedbackEntry[]> {
  const response = await fetch("/api/feedback", {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (response.status === 401) {
    throw new AuthError("セッションが切れました。もう一度ログインしてください。")
  }
  if (!response.ok) return []
  return response.json()
}

export async function dismissFeedback(token: string, id: string): Promise<void> {
  const response = await fetch(`/api/feedback/${id}/dismiss`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  })
  if (response.status === 401) {
    throw new AuthError("セッションが切れました。もう一度ログインしてください。")
  }
}
