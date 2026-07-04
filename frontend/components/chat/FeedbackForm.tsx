"use client"

import { useState } from "react"
import { AnimatePresence, motion } from "framer-motion"
import { DURATION, EASE } from "@/lib/motion"

interface FeedbackFormProps {
  isOpen: boolean
  onClose: () => void
  onSubmit: (content: string) => Promise<void>
}

/**
 * 「〜もできたらいいな」という前向きな要望・フィードバックを送るためのドロワー。
 * feedback_log.py(会話中の訂正の自動検知)とは別物で、誰でも能動的に送信できる。
 */
export function FeedbackForm({ isOpen, onClose, onSubmit }: FeedbackFormProps) {
  const [content, setContent] = useState("")
  const [sending, setSending] = useState(false)
  const [sent, setSent] = useState(false)

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
            className="fixed inset-0 z-40 bg-black/60"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: DURATION.fast, ease: EASE }}
            onClick={onClose}
          />

          <motion.div
            key="feedback-drawer"
            className="fixed inset-y-0 right-0 z-50 flex w-72 flex-col border-l border-white/10 bg-black"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ duration: DURATION.base, ease: EASE }}
          >
            <div className="flex items-center justify-between border-b border-white/10 p-4">
              <p className="font-mono text-xs uppercase tracking-widest text-white/70">
                要望・フィードバック
              </p>
              <button
                type="button"
                onClick={onClose}
                aria-label="閉じる"
                className="text-white/40 hover:text-[#c8ff00]"
              >
                ×
              </button>
            </div>

            <div className="flex flex-1 flex-col gap-3 p-4">
              <p className="font-mono text-[10px] text-white/40">
                「こんな機能あったら嬉しいな」を志粋に伝えてください。
              </p>
              <textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                rows={8}
                placeholder="例: PDFの内容も読み込めるようになったら嬉しいな"
                className="flex-1 resize-none border border-white/15 bg-transparent p-2 text-sm text-white placeholder:text-white/25 focus:border-[#c8ff00]/50 focus:outline-none"
              />
              <button
                type="button"
                disabled={sending || !content.trim()}
                onClick={handleSubmit}
                className="border border-[#c8ff00]/40 py-2 font-mono text-[10px] uppercase tracking-widest text-[#c8ff00] hover:bg-[#c8ff00]/10 disabled:opacity-40"
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
