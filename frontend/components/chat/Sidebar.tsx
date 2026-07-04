"use client"

import { cn } from "@/lib/utils"
import type { Conversation } from "@/lib/types"

interface SidebarProps {
  userName: string
  conversations: Conversation[]
  activeConversationId: number | null
  onSelectConversation: (id: number) => void
  onNewConversation: () => void
  onLogout: () => void
}

/**
 * Gemini/Claude風の会話履歴サイドバー。
 * ここに出てくるのは常にログイン中の本人の会話だけ(サーバー側でuser_idにより
 * 絞り込み済み — src/api/main.py:list_conversations参照)。
 */
export function Sidebar({
  userName,
  conversations,
  activeConversationId,
  onSelectConversation,
  onNewConversation,
  onLogout,
}: SidebarProps) {
  return (
    <div className="flex h-full w-64 shrink-0 flex-col border-r border-white/10 bg-black">
      <div className="p-4">
        <button
          type="button"
          onClick={onNewConversation}
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
            onClick={() => onSelectConversation(conversation.id)}
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
        <p className="truncate font-mono text-xs text-white/40">{userName}</p>
        <button
          type="button"
          onClick={onLogout}
          className="mt-2 font-mono text-[10px] uppercase tracking-widest text-white/25 underline underline-offset-4 hover:text-white/60"
        >
          ログアウト
        </button>
      </div>
    </div>
  )
}
