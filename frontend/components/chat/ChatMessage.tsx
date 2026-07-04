"use client"

import { AnimatePresence, motion } from "framer-motion"
import { cn } from "@/lib/utils"
import { DURATION, EASE } from "@/lib/motion"
import type { ChatMessage as ChatMessageType } from "@/lib/types"
import { MarkdownContent } from "./MarkdownContent"
import { PendingPulse } from "./PendingPulse"
import { ThinkingAccordion } from "./ThinkingAccordion"

interface ChatMessageProps {
  message: ChatMessageType
  isStreamingNow?: boolean
}

/**
 * マウント時に一度だけ、フェード+わずかな上方向のスライドで現れる。
 * ユーザー発言→志粋の発言の2件がほぼ同時に追加されても、それぞれ独立して
 * マウントされるため、自然な段階的リビールになる(ストリーミング中の
 * content更新では再アニメーションしない — フレーマーモーションはマウント時のみ発火する)。
 */
export function ChatMessage({ message, isStreamingNow }: ChatMessageProps) {
  const isUser = message.role === "user"

  return (
    <motion.div
      className="flex w-full justify-start"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      // ユーザー発言と志粋の発言は同時に配列へ追加されるため、志粋側にわずかな
      // delayを付けることで「ユーザー→志粋」の順で現れる段階的リビールにする
      transition={{ duration: DURATION.fast, ease: EASE, delay: isUser ? 0 : 0.1 }}
    >
      <div className="max-w-[85%] text-left sm:max-w-[70%]">
        {/* 送信直後、thinking/contentのどちらもまだ届いていない空白期間の
            「止まっているわけではない」表示。最初の1バイトが届いた瞬間に消える。 */}
        {!isUser && isStreamingNow && !message.thinking && !message.content && <PendingPulse />}
        {/* 応答が完了したら思考中の表示は消す(生成中のこのメッセージだけに表示する) */}
        <AnimatePresence>
          {!isUser && isStreamingNow && message.thinking && (
            <motion.div
              key="thinking"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: DURATION.fast, ease: EASE }}
            >
              <ThinkingAccordion thinking={message.thinking} />
            </motion.div>
          )}
        </AnimatePresence>
        <MarkdownContent
          content={message.content}
          className={isUser ? "text-white/90" : "text-white/60"}
        />
      </div>
    </motion.div>
  )
}
