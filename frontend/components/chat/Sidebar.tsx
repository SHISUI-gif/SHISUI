"use client"

import { AnimatePresence, motion } from "framer-motion"
import { cn } from "@/lib/utils"
import { DURATION, EASE } from "@/lib/motion"
import type { Conversation } from "@/lib/types"

interface SidebarProps {
  isOpen: boolean
  onClose: () => void
  userName: string
  conversations: Conversation[]
  activeConversationId: number | null
  onSelectConversation: (id: number) => void
  onNewConversation: () => void
  onOpenActivityLog: () => void
  onLogout: () => void
}

/**
 * Gemini/Claude風の会話履歴サイドバー。
 *
 * 常時幅を占有する固定カラムだと、実際にチャットしている最中は画面を圧迫して
 * 使いにくいという指摘を受け、左上のボタンで開閉するスライド式のドロワーに
 * した(会話中の主役はチャット本文であって、履歴の一覧はあくまで補助的な
 * ナビゲーションのため)。会話を選ぶ・新規作成すると自動で閉じる。
 * ここに出てくるのは常にログイン中の本人の会話だけ(サーバー側でuser_idにより
 * 絞り込み済み — src/api/main.py:list_conversations参照)。
 */
export function Sidebar({
  isOpen,
  onClose,
  userName,
  conversations,
  activeConversationId,
  onSelectConversation,
  onNewConversation,
  onOpenActivityLog,
  onLogout,
}: SidebarProps) {
  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* 背景オーバーレイ。タップ/クリックで閉じる(特にスマホ幅で重要) */}
          <motion.div
            key="backdrop"
            className="fixed inset-0 z-40 bg-black/60"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: DURATION.fast, ease: EASE }}
            onClick={onClose}
          />

          <motion.div
            key="drawer"
            className="fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-white/10 bg-black"
            initial={{ x: "-100%" }}
            animate={{ x: 0 }}
            exit={{ x: "-100%" }}
            transition={{ duration: DURATION.base, ease: EASE }}
          >
            <div className="p-4">
              <button
                type="button"
                onClick={() => {
                  onNewConversation()
                  onClose()
                }}
                className="w-full border border-white/15 py-2 font-mono text-xs uppercase tracking-widest text-white/70 transition-colors hover:border-[#c8ff00]/50 hover:text-[#c8ff00]"
              >
                + 新しい会話
              </button>
            </div>

            <div className="flex-1 overflow-y-auto px-2">
              {conversations.length === 0 && (
                <p className="px-2 py-4 font-mono text-[10px] text-white/25">まだ会話がありません</p>
              )}
              {conversations.map((conversation) => (
                <button
                  key={conversation.id}
                  type="button"
                  onClick={() => {
                    onSelectConversation(conversation.id)
                    onClose()
                  }}
                  className={cn(
                    "block w-full truncate rounded px-3 py-2 text-left text-sm transition-colors",
                    conversation.id === activeConversationId
                      ? "bg-white/10 text-white"
                      : "text-white/50 hover:bg-white/5 hover:text-white/80",
                  )}
                >
                  {conversation.title}
                </button>
              ))}
            </div>

            <div className="border-t border-white/10 p-4">
              <button
                type="button"
                onClick={() => {
                  onOpenActivityLog()
                  onClose()
                }}
                className="mb-3 font-mono text-[10px] uppercase tracking-widest text-white/40 hover:text-[#c8ff00]"
              >
                活動ログ
              </button>
              <p className="truncate font-mono text-xs text-white/40">{userName}</p>
              <button
                type="button"
                onClick={onLogout}
                className="mt-2 font-mono text-[10px] uppercase tracking-widest text-white/25 underline underline-offset-4 hover:text-white/60"
              >
                ログアウト
              </button>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
