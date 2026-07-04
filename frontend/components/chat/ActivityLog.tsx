"use client"

import { AnimatePresence, motion } from "framer-motion"
import { DURATION, EASE } from "@/lib/motion"
import type { ActivityEntry } from "@/lib/types"

interface ActivityLogProps {
  isOpen: boolean
  onClose: () => void
  activities: ActivityEntry[]
}

const KIND_LABEL: Record<ActivityEntry["kind"], string> = {
  sleep: "💤 睡眠モード",
  study: "📚 夜間修行",
  debate: "💬 自律討論",
}

/**
 * 睡眠モード・夜間修行・自律討論など、志粋が那由多さんの見ていないところで
 * 自律的に行っている活動を時系列で見せるパネル。特定の友達の会話ではなく
 * 志粋自身の活動なので、誰がログインしても同じ内容が見える
 * (src/api/main.py:get_activity参照)。
 */
export function ActivityLog({ isOpen, onClose, activities }: ActivityLogProps) {
  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            key="activity-backdrop"
            className="fixed inset-0 z-40 bg-black/60"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: DURATION.fast, ease: EASE }}
            onClick={onClose}
          />

          <motion.div
            key="activity-drawer"
            className="fixed inset-y-0 right-0 z-50 flex w-72 flex-col border-l border-white/10 bg-black"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ duration: DURATION.base, ease: EASE }}
          >
            <div className="flex items-center justify-between border-b border-white/10 p-4">
              <p className="font-mono text-xs uppercase tracking-widest text-white/70">活動ログ</p>
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
              {activities.length === 0 && (
                <p className="font-mono text-[10px] text-white/25">
                  まだ活動記録がありません(1日1回の睡眠モードで記録されます)
                </p>
              )}
              <div className="flex flex-col gap-4">
                {activities.map((activity, index) => (
                  <div key={`${activity.timestamp}-${index}`} className="border-b border-white/5 pb-3">
                    <p className="font-mono text-[10px] uppercase tracking-wider text-[#c8ff00]/70">
                      {KIND_LABEL[activity.kind]}
                    </p>
                    <p className="mt-1 text-sm text-white/70">{activity.summary}</p>
                    <p className="mt-1 font-mono text-[10px] text-white/25">{activity.timestamp}</p>
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
