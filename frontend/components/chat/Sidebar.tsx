"use client"

import { AnimatePresence, motion } from "framer-motion"
import { AvatarDisplay } from "@/components/AvatarDisplay"
import { GlowBlob } from "@/components/GlowBlob"
import { cn } from "@/lib/utils"
import { DURATION, EASE } from "@/lib/motion"
import type { AvatarItem, Conversation } from "@/lib/types"

/**
 * 会話一覧の各行をドロワー本体のスライドが落ち着いた後に少し遅れて
 * カスケード表示させるためのvariants。app/page.tsxのstaggerContainer/fadeUpと
 * 同じ考え方(EASEを共有・小さめのstaggerChildren)をリスト項目向けに調整したもの。
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

interface SidebarProps {
  isOpen: boolean
  onClose: () => void
  userName: string
  isOwner: boolean
  sessionCount: number
  unlockCount: number
  mood: string | null
  unlockedItems: AvatarItem[]
  conversations: Conversation[]
  activeConversationId: number | null
  onSelectConversation: (id: number) => void
  onDeleteConversation: (id: number) => void
  onNewConversation: () => void
  onOpenActivityLog: () => void
  onOpenEvolutionProposals: () => void
  onOpenFeedbackForm: () => void
  onOpenFeedbackReview: () => void
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
  isOwner,
  sessionCount,
  unlockCount,
  mood,
  unlockedItems,
  conversations,
  activeConversationId,
  onSelectConversation,
  onDeleteConversation,
  onNewConversation,
  onOpenActivityLog,
  onOpenEvolutionProposals,
  onOpenFeedbackForm,
  onOpenFeedbackReview,
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
            className="fixed inset-y-4 left-4 z-50 flex w-64 flex-col overflow-hidden rounded-3xl border border-white/10 bg-[#0a0a0a] shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]"
            initial={{ x: "-120%" }}
            animate={{ x: 0 }}
            exit={{ x: "-120%" }}
            transition={{ duration: DURATION.base, ease: EASE }}
          >
            <GlowBlob className="-left-1/4 -top-1/4 h-2/3 w-2/3 bg-[#b8935a]/[0.08]" />

            <div className="relative p-4">
              <button
                type="button"
                onClick={() => {
                  onNewConversation()
                  onClose()
                }}
                className="w-full border border-white/15 py-2 font-mono text-xs uppercase tracking-widest text-white/70 transition-colors hover:border-[#b8935a]/50 hover:text-[#b8935a]"
              >
                + 新しい会話
              </button>

              {/* ホーム画面(chatOpen=false)を閉じるとAvatarDisplay自体が
                  アンマウントされ、会話中は自分のアバターが一切見えなくなって
                  いた(那由多さんの指摘「新しく会話を開かないと自分のアバター
                  を見れない」)。チャット中でも常に開けるサイドバーに、小さな
                  縮小表示を常設する。 */}
              <div className="mt-3 flex items-center gap-3 border-t border-white/10 pt-3">
                <div className="h-16 w-16 shrink-0 overflow-hidden rounded-full border border-white/10 bg-white/5">
                  <AvatarDisplay unlockedItems={unlockedItems} mood={mood} />
                </div>
                <p className="min-w-0 truncate font-mono text-[10px] text-white/40">
                  {unlockedItems.length > 0
                    ? unlockedItems[unlockedItems.length - 1].display_name
                    : "素体"}
                </p>
              </div>

              {/* ホーム画面から移した統計(会話数・解除数・ムード)。
                  ホームは「情報より志粋の存在感」を優先する1枚絵にしたため、
                  数値情報はこちらに集約している */}
              <div className="mt-3 grid grid-cols-3 gap-2 border-t border-white/10 pt-3">
                <div className="flex flex-col items-start gap-0.5">
                  <span className="font-mono text-sm text-[#b8935a]">{sessionCount}</span>
                  <span className="font-mono text-[8px] uppercase tracking-widest text-white/30">
                    Sessions
                  </span>
                </div>
                <div className="flex flex-col items-start gap-0.5">
                  <span className="font-mono text-sm text-[#b8935a]">{unlockCount}</span>
                  <span className="font-mono text-[8px] uppercase tracking-widest text-white/30">
                    Unlocks
                  </span>
                </div>
                <div className="flex flex-col items-start gap-0.5">
                  <span className="truncate font-mono text-sm text-[#b8935a]">{mood ?? "—"}</span>
                  <span className="font-mono text-[8px] uppercase tracking-widest text-white/30">
                    Mood
                  </span>
                </div>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto px-2">
              {conversations.length === 0 && (
                <p className="px-2 py-4 font-mono text-[10px] text-white/25">まだ会話がありません</p>
              )}
              <motion.div variants={listContainer} initial="hidden" animate="visible">
                {conversations.map((conversation) => (
                  <motion.div
                    key={conversation.id}
                    variants={listItem}
                    className="group flex items-center"
                  >
                    <button
                      type="button"
                      onClick={() => {
                        onSelectConversation(conversation.id)
                        onClose()
                      }}
                      className={cn(
                        "block min-w-0 flex-1 truncate px-3 py-2 text-left text-sm transition-colors",
                        conversation.id === activeConversationId
                          ? "bg-white/10 text-white"
                          : "text-white/50 hover:bg-white/5 hover:text-white/80",
                      )}
                    >
                      {conversation.title}
                    </button>
                    <button
                      type="button"
                      aria-label="この会話を削除"
                      onClick={(event) => {
                        event.stopPropagation()
                        if (window.confirm(`「${conversation.title}」を削除しますか?`)) {
                          onDeleteConversation(conversation.id)
                        }
                      }}
                      className="shrink-0 px-2 py-2 text-white/20 opacity-0 transition-opacity hover:text-red-400 group-hover:opacity-100"
                    >
                      ✕
                    </button>
                  </motion.div>
                ))}
              </motion.div>
            </div>

            <div className="border-t border-white/10 p-4">
              <button
                type="button"
                onClick={() => {
                  onOpenActivityLog()
                  onClose()
                }}
                className="mb-3 block w-full text-left font-mono text-[10px] uppercase tracking-widest text-white/40 hover:text-[#b8935a]"
              >
                活動ログ
              </button>
              <button
                type="button"
                onClick={() => {
                  onOpenFeedbackForm()
                  onClose()
                }}
                className="mb-3 block w-full text-left font-mono text-[10px] uppercase tracking-widest text-white/40 hover:text-[#b8935a]"
              >
                要望・フィードバックを送る
              </button>
              {isOwner && (
                <div className="mb-3 border-t border-white/10 pt-3">
                  <p className="mb-2 font-mono text-[9px] uppercase tracking-widest text-white/25">
                    オーナー
                  </p>
                  <button
                    type="button"
                    onClick={() => {
                      onOpenFeedbackReview()
                      onClose()
                    }}
                    className="block w-full text-left font-mono text-[10px] uppercase tracking-widest text-white/40 hover:text-[#b8935a]"
                  >
                    フィードバック確認
                  </button>
                  <div className="mt-3 border-t border-white/5 pt-3">
                    <button
                      type="button"
                      onClick={() => {
                        onOpenEvolutionProposals()
                        onClose()
                      }}
                      className="block w-full text-left font-mono text-[10px] uppercase tracking-widest text-white/40 hover:text-[#b8935a]"
                    >
                      承認待ちの修正案
                    </button>
                  </div>
                </div>
              )}
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
