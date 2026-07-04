"use client"

import { AnimatePresence, motion } from "framer-motion"
import { cn } from "@/lib/utils"
import { DURATION, EASE } from "@/lib/motion"
import type { UserFeedbackEntry } from "@/lib/types"

interface FeedbackReviewProps {
  isOpen: boolean
  onClose: () => void
  entries: UserFeedbackEntry[]
  onDismiss: (id: string) => Promise<void>
}

/**
 * 友達から送られた要望・フィードバックの一覧をオーナーが確認するパネル。
 * 「志粋が生成したコード修正案(EvolutionProposals)」とは概念的に別物
 * (こちらは人間からの要望)なので、専用のドロワーとして分けている。
 */
export function FeedbackReview({ isOpen, onClose, entries, onDismiss }: FeedbackReviewProps) {
  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            key="feedback-review-backdrop"
            className="fixed inset-0 z-40 bg-black/60"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: DURATION.fast, ease: EASE }}
            onClick={onClose}
          />

          <motion.div
            key="feedback-review-drawer"
            className="fixed inset-y-0 right-0 z-50 flex w-72 flex-col border-l border-white/10 bg-black"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ duration: DURATION.base, ease: EASE }}
          >
            <div className="flex items-center justify-between border-b border-white/10 p-4">
              <p className="font-mono text-xs uppercase tracking-widest text-white/70">
                要望・フィードバック確認
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

            <div className="flex-1 overflow-y-auto p-4">
              {entries.length === 0 && (
                <p className="font-mono text-[10px] text-white/25">まだ届いていません</p>
              )}
              <div className="flex flex-col gap-4">
                {entries.map((entry) => (
                  <div
                    key={entry.id}
                    className={cn(
                      "border-b border-white/5 pb-3",
                      entry.reviewed && "opacity-40",
                    )}
                  >
                    <p className="font-mono text-[10px] uppercase tracking-wider text-[#c8ff00]/70">
                      {entry.user_name}
                    </p>
                    <p className="mt-1 text-sm text-white/80">{entry.content}</p>
                    <p className="mt-1 font-mono text-[10px] text-white/25">{entry.timestamp}</p>
                    {!entry.reviewed && (
                      <button
                        type="button"
                        onClick={() => onDismiss(entry.id)}
                        className="mt-2 font-mono text-[10px] uppercase tracking-widest text-white/40 hover:text-[#c8ff00]"
                      >
                        既読にする
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
