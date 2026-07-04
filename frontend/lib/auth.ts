import type { AuthUser } from "./types"

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
