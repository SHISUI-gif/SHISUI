import { AuthError } from "./api"
import type { AvatarState } from "./types"

export async function getAvatarState(token: string): Promise<AvatarState> {
  const response = await fetch("/api/avatar", {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (response.status === 401) {
    throw new AuthError("セッションが切れました。もう一度ログインしてください。")
  }
  if (!response.ok) return { unlockedItems: [], mood: null, selectedSlug: null }
  const body = await response.json()
  return { unlockedItems: body.unlocked_items, mood: body.mood, selectedSlug: body.selected_slug }
}

export async function selectAvatarItem(token: string, slug: string): Promise<boolean> {
  const response = await fetch("/api/avatar/select", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify({ slug }),
  })
  if (response.status === 401) {
    throw new AuthError("セッションが切れました。もう一度ログインしてください。")
  }
  return response.ok
}
