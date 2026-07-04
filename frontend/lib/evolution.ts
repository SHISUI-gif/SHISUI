import { AuthError } from "./api"
import type { EvolutionProposal } from "./types"

export async function getPendingProposals(token: string): Promise<EvolutionProposal[]> {
  const response = await fetch("/api/evolution/proposals", {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (response.status === 401) {
    throw new AuthError("セッションが切れました。もう一度ログインしてください。")
  }
  if (!response.ok) return []
  return response.json()
}

export async function applyProposal(
  token: string,
  id: string,
): Promise<{ ok: boolean; message: string }> {
  const response = await fetch(`/api/evolution/proposals/${id}/apply`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  })
  if (response.status === 401) {
    throw new AuthError("セッションが切れました。もう一度ログインしてください。")
  }
  return response.json()
}

export async function rejectProposal(token: string, id: string): Promise<{ ok: boolean }> {
  const response = await fetch(`/api/evolution/proposals/${id}/reject`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  })
  if (response.status === 401) {
    throw new AuthError("セッションが切れました。もう一度ログインしてください。")
  }
  return response.json()
}
