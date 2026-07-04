import { AuthError } from "./api"
import type { AuthUser, CurrentUser } from "./types"

const STORAGE_KEY = "shisui_auth"

/**
 * ログイン状態をlocalStorageに保存する。ブラウザを消したらこれも消えるが、
 * サーバー側に会話・記憶は残っているため、同じ名前+パスワードで再ログインすれば
 * そのまま続きから使える(Gemini/Claude/ChatGPTと同じ挙動)。
 */
export function saveAuth(user: AuthUser): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(user))
}

export function loadAuth(): AuthUser | null {
  if (typeof window === "undefined") return null
  const raw = localStorage.getItem(STORAGE_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as AuthUser
  } catch {
    return null
  }
}

export function clearAuth(): void {
  localStorage.removeItem(STORAGE_KEY)
}

async function postAuth(path: "register" | "login", name: string, password: string): Promise<AuthUser> {
  const response = await fetch(`/api/auth/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, password }),
  })

  const body = await response.json()
  if (!response.ok) {
    throw new Error(body.detail || "認証に失敗しました。")
  }

  return { token: body.token, userId: body.user_id, name: body.name }
}

export function register(name: string, password: string): Promise<AuthUser> {
  return postAuth("register", name, password)
}

export function login(name: string, password: string): Promise<AuthUser> {
  return postAuth("login", name, password)
}

/**
 * オーナー判定(is_owner)は、ログイン/登録レスポンスと違ってlocalStorageに
 * キャッシュしない。OWNER_USER_NAMEが変わった場合に古い判定が残らないよう、
 * 毎回このエンドポイントに問い合わせる。
 */
export async function getCurrentUser(token: string): Promise<CurrentUser> {
  const response = await fetch("/api/auth/me", {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (response.status === 401) {
    throw new AuthError("セッションが切れました。もう一度ログインしてください。")
  }
  const body = await response.json()
  return { userId: body.user_id, name: body.name, isOwner: body.is_owner }
}
