import { AuthError } from "./api"
import type { ActivityEntry } from "./types"

export async function getRecentActivity(token: string): Promise<ActivityEntry[]> {
  const response = await fetch("/api/activity", {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (response.status === 401) {
    throw new AuthError("セッションが切れました。もう一度ログインしてください。")
  }
  if (!response.ok) return []
  const body = await response.json()
  return body.activities
}

export async function getSleepStatus(token: string): Promise<boolean> {
  const response = await fetch("/api/activity/sleep-status", {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!response.ok) return false
  const body = await response.json()
  return Boolean(body.in_progress)
}
