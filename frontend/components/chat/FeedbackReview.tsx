"use client"

import { useEffect, useRef, useState } from "react"
import { AnimatePresence, motion } from "framer-motion"
import { GlowBlob } from "@/components/GlowBlob"
import { cn } from "@/lib/utils"
import { DURATION, EASE } from "@/lib/motion"
import type { UserFeedbackEntry } from "@/lib/types"

/**
 * 一覧の各カードをモーダルのスライドが落ち着いた後に少し遅れてカスケード表示
 * させるためのvariants(ActivityLog.tsxと同じ考え方)。
 */
const listContainer = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.04, delayChildren: 0.2 },
  },
}

const listItem = {
  hidden: { opacity: 0, y: 10 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: DURATION.fast, ease: EASE },
  },
}

interface FeedbackReviewProps {
  isOpen: boolean
  onClose: () => void
  entries: UserFeedbackEntry[]
  onDismiss: (id: string) => Promise<void>
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
 * 友達から送られた要望・フィードバックの一覧をオーナーが確認するパネル。
 * 「志粋が生成したコード修正案(EvolutionProposals)」とは概念的に別物
 * (こちらは人間からの要望)なので、専用のモーダルとして分けている。
 * ActivityLog.tsxと同じカード構成に統一。
 */
export function FeedbackReview({ isOpen, onClose, entries, onDismiss }: FeedbackReviewProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const glow = useCursorGlow(containerRef)

  const unreviewedCount = entries.filter((e) => !e.reviewed).length
  const uniqueUsers = new Set(entries.map((e) => e.user_name)).size
  const latest = entries[0]

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            key="feedback-review-backdrop"
            className="fixed inset-0 z-40 bg-black/80"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: DURATION.fast, ease: EASE }}
            onClick={onClose}
          />

          <motion.div
            key="feedback-review-modal"
            ref={containerRef}
            className="fixed inset-4 z-50 overflow-hidden rounded-3xl border border-white/10 bg-[#0a0a0a] shadow-[inset_0_1px_0_rgba(255,255,255,0.08)] sm:inset-10 lg:inset-16"
            initial={{ opacity: 0, scale: 0.97 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.97 }}
            transition={{ duration: DURATION.base, ease: EASE }}
          >
            {/* 立体感を出すための、ぼかしたアクセントカラーの光の層+粒状テクスチャ(背景) */}
            <GlowBlob className="-right-1/4 -top-1/3 h-[70%] w-[70%] bg-[#b8935a]/[0.10]" />
            <GlowBlob className="-bottom-1/3 -left-1/4 h-[60%] w-[60%] bg-[#b8935a]/[0.07]" />
            <div
              aria-hidden="true"
              className="pointer-events-none absolute inset-0 opacity-20 blur-3xl transition-[background] duration-150"
              style={{
                background: glow
                  ? `radial-gradient(420px circle at ${glow.x}px ${glow.y}px, #b8935a, transparent 70%)`
                  : "none",
              }}
            />

            <button
              type="button"
              onClick={onClose}
              aria-label="閉じる"
              className="absolute right-4 top-4 z-10 flex min-h-11 min-w-11 items-center justify-center rounded-full text-white/40 hover:bg-white/5 hover:text-[#b8935a]"
            >
              ×
            </button>

            <div className="relative flex h-full flex-col overflow-y-auto p-6 sm:p-10">
              <p className="font-mono text-xs uppercase tracking-widest text-white/70">
                要望・フィードバック確認
              </p>

              <div className="mt-8 grid gap-4 lg:grid-cols-[2fr_1fr]">
                {/* 左: 未読件数を大きく見せる概要カード */}
                <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-6 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] backdrop-blur-xl sm:p-8">
                  <p className="font-mono text-[10px] uppercase tracking-wider text-[#b8935a]/70">
                    {latest ? latest.user_name : "まだ届いていません"}
                  </p>
                  <p className="mt-2 text-lg text-white/80">
                    {latest?.content ?? "友達からの要望・フィードバックがここに届きます"}
                  </p>

                  <div className="flex items-center justify-center py-8">
                    <div className="relative flex h-40 w-40 items-center justify-center rounded-full border border-dashed border-white/20 sm:h-48 sm:w-48">
                      <GlowBlob className="inset-4 bg-[#b8935a]/[0.14]" />
                      <div className="relative text-center">
                        <p className="font-[family-name:var(--font-syne)] text-4xl font-bold text-white">
                          {unreviewedCount}
                        </p>
                        <p className="mt-1 font-mono text-[9px] uppercase tracking-widest text-white/40">
                          未読
                        </p>
                      </div>
                    </div>
                  </div>
                </div>

                {/* 右: 内訳 */}
                <div className="flex flex-col gap-4">
                  <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-6 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] backdrop-blur-xl">
                    <p className="font-[family-name:var(--font-syne)] text-lg font-bold text-white">概要</p>
                    <div className="mt-4 space-y-3">
                      <div className="flex items-center justify-between font-mono text-xs">
                        <span className="text-white/40">総件数</span>
                        <span className="text-white/70">{entries.length}件</span>
                      </div>
                      <div className="flex items-center justify-between font-mono text-xs">
                        <span className="text-white/40">送信者数</span>
                        <span className="text-white/70">{uniqueUsers}人</span>
                      </div>
                    </div>
                  </div>

                  <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-6 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] backdrop-blur-xl">
                    <p className="font-[family-name:var(--font-syne)] text-lg font-bold text-white">最新</p>
                    <div className="mt-4 space-y-3">
                      <div className="flex items-center justify-between font-mono text-xs">
                        <span className="text-white/40">最新の受信</span>
                        <span className="text-white/70">{latest?.timestamp ?? "—"}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* 下: 全件の一覧 */}
              <div className="mt-10 rounded-2xl border border-white/10 bg-white/[0.02] p-6 backdrop-blur-xl">
                <p className="font-mono text-[10px] uppercase tracking-widest text-white/40">
                  すべての要望・フィードバック
                </p>
                {entries.length === 0 && (
                  <p className="mt-4 font-mono text-[10px] text-white/25">まだ届いていません</p>
                )}
                <motion.div
                  className="mt-4 flex flex-col gap-4"
                  variants={listContainer}
                  initial="hidden"
                  animate="visible"
                >
                  {entries.map((entry) => (
                    <motion.div
                      key={entry.id}
                      variants={listItem}
                      className={cn(
                        "border-b border-white/5 pb-3",
                        entry.reviewed && "opacity-40",
                      )}
                    >
                      <p className="font-mono text-[10px] uppercase tracking-wider text-[#b8935a]/70">
                        {entry.user_name}
                      </p>
                      <p className="mt-1 text-sm text-white/80">{entry.content}</p>
                      <p className="mt-1 font-mono text-[10px] text-white/25">{entry.timestamp}</p>
                      {!entry.reviewed && (
                        <button
                          type="button"
                          onClick={() => onDismiss(entry.id)}
                          className="mt-2 font-mono text-[10px] uppercase tracking-widest text-white/40 hover:text-[#b8935a]"
                        >
                          既読にする
                        </button>
                      )}
                    </motion.div>
                  ))}
                </motion.div>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
