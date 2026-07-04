"use client"

import { useState, type FormEvent } from "react"
import { motion } from "framer-motion"
import { login, register } from "@/lib/auth"
import { DURATION, EASE } from "@/lib/motion"
import type { AuthUser } from "@/lib/types"

interface LoginFormProps {
  onAuthenticated: (user: AuthUser) => void
}

/**
 * 名前+簡易パスワードでのログイン/新規登録画面。
 * ブラウザを消してもサーバー側に会話・記憶は残るので、同じ名前+パスワードで
 * 再ログインすれば続きから使える(本格的な認証ではなく、友達同士の
 * 会話を混ぜない/覗き見しないための最低限の区別)。
 */
export function LoginForm({ onAuthenticated }: LoginFormProps) {
  const [mode, setMode] = useState<"login" | "register">("login")
  const [name, setName] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const user = mode === "login" ? await login(name, password) : await register(name, password)
      onAuthenticated(user)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <motion.div
      className="flex min-h-screen items-center justify-center bg-black px-6"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: DURATION.base, ease: EASE }}
    >
      <div className="w-full max-w-sm">
        <p className="font-[family-name:var(--font-syne)] text-2xl font-bold tracking-tight text-white">
          SHISUI
        </p>
        <span className="mt-1 block h-px w-10 origin-left bg-[#c8ff00]" />
        <p className="mt-6 font-mono text-xs tracking-wider text-white/40 uppercase">
          {mode === "login" ? "おかえりなさい" : "はじめまして"}
        </p>

        <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="名前"
            required
            className="border-b border-white/15 bg-transparent px-0 py-2 text-base text-white/90 outline-none placeholder:text-white/25 focus:border-[#c8ff00]/60 sm:text-sm"
          />
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="パスワード"
            required
            className="border-b border-white/15 bg-transparent px-0 py-2 text-base text-white/90 outline-none placeholder:text-white/25 focus:border-[#c8ff00]/60 sm:text-sm"
          />

          {error && <p className="text-xs text-red-400">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="mt-2 bg-[#c8ff00] py-2 font-mono text-xs uppercase tracking-widest text-black transition-opacity hover:opacity-80 disabled:opacity-40"
          >
            {loading ? "..." : mode === "login" ? "ログイン" : "登録する"}
          </button>
        </form>

        <button
          type="button"
          onClick={() => {
            setMode(mode === "login" ? "register" : "login")
            setError(null)
          }}
          className="mt-4 font-mono text-xs text-white/40 underline underline-offset-4 hover:text-white/70"
        >
          {mode === "login" ? "はじめての人はこちら(新規登録)" : "すでにアカウントがある方はこちら"}
        </button>
      </div>
    </motion.div>
  )
}
