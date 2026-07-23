"use client"

import { useEffect, useRef, useState } from "react"
import { AnimatePresence, motion } from "framer-motion"
import { GlowBlob } from "@/components/GlowBlob"
import { DURATION, EASE } from "@/lib/motion"

interface FeedbackFormProps {
  isOpen: boolean
  onClose: () => void
  onSubmit: (content: string) => Promise<void>
}

/**
 * マウス位置に追従する、ぼかしたアクセントカラーのグロー(ActivityLog.tsxと同じ演出)。
 */
function useCursorGlow(containerRef: React.RefObject<HTMLDivElement | null>) {
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return

    const handleMove = (event: MouseEvent) => {
      const rect = el.getBoundingClientRect()
      setPos({ x: event.clientX - rect.left, y: event.clientY - rect.top })
    }

    el.addEventListener("mousemove", handleMove)
    return () => el.removeEventListener("mousemove", handleMove)
  }, [containerRef])

  return pos
}

/**
 * 「〜もできたらいいな」という前向きな要望・フィードバックを送るための送信フォーム。
 * feedback_log.py(会話中の訂正の自動検知)とは別物で、誰でも能動的に送信できる。
 * 一覧系のドロワー(ActivityLog等)とは違い単純な送信フォームなので、統計カードは
 * 持たず、同じモーダルの外枠(角丸ゼロ・カーソル追従グロー)だけ揃える。
 */
export function FeedbackForm({ isOpen, onClose, onSubmit }: FeedbackFormProps) {
  const [content, setContent] = useState("")
  const [sending, setSending] = useState(false)
  const [sent, setSent] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const glow = useCursorGlow(containerRef)

  const handleSubmit = async () => {
    if (!content.trim()) return
    setSending(true)
    try {
      await onSubmit(content.trim())
      setContent("")
      setSent(true)
      setTimeout(() => setSent(false), 2000)
    } finally {
      setSending(false)
    }
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            key="feedback-backdrop"
            className="fixed inset-0 z-40 bg-black/80"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: DURATION.fast, ease: EASE }}
            onClick={onClose}
          />

          <motion.div
            key="feedback-modal"
            ref={containerRef}
            className="fixed left-1/2 top-1/2 z-50 w-[calc(100%-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 overflow-hidden rounded-3xl border border-white/10 bg-[#0a0a0a] shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]"
            initial={{ opacity: 0, scale: 0.97 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.97 }}
            transition={{ duration: DURATION.base, ease: EASE }}
          >
            {/* 立体感を出すための、ぼかしたアクセントカラーの光の層+粒状テクスチャ(背景) */}
            <GlowBlob className="-right-1/3 -top-1/2 h-[80%] w-[80%] bg-[#b8935a]/[0.10]" />
            <div
              aria-hidden="true"
              className="pointer-events-none absolute inset-0 opacity-20 blur-3xl transition-[background] duration-150"
              style={{
                background: glow
                  ? `radial-gradient(280px circle at ${glow.x}px ${glow.y}px, #b8935a, transparent 70%)`
                  : "none",
              }}
            />

            <div className="relative flex items-center justify-between border-b border-white/10 p-4">
              <p className="font-mono text-xs uppercase tracking-widest text-white/70">
                要望・フィードバック
              </p>
              <button
                type="button"
                onClick={onClose}
                aria-label="閉じる"
                className="flex min-h-11 min-w-11 items-center justify-center rounded-full text-white/40 hover:bg-white/5 hover:text-[#b8935a]"
              >
                ×
              </button>
            </div>

            <div className="relative flex flex-col gap-3 p-4">
              <p className="font-mono text-[10px] text-white/40">
                「こんな機能あったら嬉しいな」を志粋に伝えてください。
              </p>
              <textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                rows={8}
                placeholder="例: PDFの内容も読み込めるようになったら嬉しいな"
                className="resize-none rounded-2xl border border-white/15 bg-white/[0.02] p-3 text-sm text-white placeholder:text-white/25 focus:border-[#b8935a]/50 focus:outline-none"
              />
              <button
                type="button"
                disabled={sending || !content.trim()}
                onClick={handleSubmit}
                className="rounded-full border border-[#b8935a]/40 py-2 font-mono text-[10px] uppercase tracking-widest text-[#b8935a] hover:bg-[#b8935a]/10 disabled:opacity-40"
              >
                {sent ? "送信しました" : sending ? "送信中..." : "送信"}
              </button>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
