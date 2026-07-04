import { AuthError } from "./api"
import type { AvatarItem } from "./types"

export async function getAvatarState(token: string): Promise<AvatarItem[]> {
  const response = await fetch("/api/avatar", {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (response.status === 401) {
    throw new AuthError("セッションが切れました。もう一度ログインしてください。")
  }
  if (!response.ok) return []
  const body = await response.json()
  return body.unlocked_items
}
