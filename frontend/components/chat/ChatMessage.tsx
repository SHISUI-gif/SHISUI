"use client"

import { AnimatePresence, motion } from "framer-motion"
import { DURATION, EASE } from "@/lib/motion"
import type { ChatMessage as ChatMessageType } from "@/lib/types"
import { MarkdownContent } from "./MarkdownContent"
import { ThinkingAccordion } from "./ThinkingAccordion"

interface ChatMessageProps {
  message: ChatMessageType
  isStreamingNow?: boolean
  /** アシスタント発言のみ。このターンが何番目かをゴースト数字として背景に薄く出す
   * (ヘッダーの「№ 04」と同じ数字を指す — ヘッダーとメッセージリストを
   * 1つの体系として見せるための、唯一の再利用モチーフ)。 */
  turnIndex?: number
}

/**
 * マウント時に一度だけ、フェード+わずかな上方向のスライドで現れる。
 * ユーザー発言→志粋の発言の2件がほぼ同時に追加されても、それぞれ独立して
 * マウントされるため、自然な段階的リビールになる(ストリーミング中の
 * content更新では再アニメーションしない — フレーマーモーションはマウント時のみ発火する)。
 *
 * ユーザー発言は「吹き出し」ではなく右寄せの短いプロンプト、志粋の発言は
 * 左に細いグラデーションの脊柱(spine)が入った全幅の原稿ブロックとして見せる
 * — 双方を同じ形の吹き出しで鏡合わせにするのをやめ、「問いかけ」と
 * 「応答の文章」という非対称な役割の違いをレイアウトそのもので表現する。
 */
export function ChatMessage({ message, isStreamingNow, turnIndex }: ChatMessageProps) {
  const isUser = message.role === "user"

  if (isUser) {
    return (
      <motion.div
        className="flex w-full justify-end"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: DURATION.fast, ease: EASE }}
      >
        <div className="ml-auto max-w-[80%] text-right">
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#b8935a]/60">YOU</p>
          <p className="mt-1 text-base font-medium leading-snug text-white">{message.content}</p>
        </div>
      </motion.div>
    )
  }

  return (
    <motion.div
      className="flex w-full justify-start"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      // ユーザー発言と志粋の発言は同時に配列へ追加されるため、志粋側にわずかな
      // delayを付けることで「ユーザー→志粋」の順で現れる段階的リビールにする
      transition={{ duration: DURATION.fast, ease: EASE, delay: 0.1 }}
    >
      <div className="relative w-full max-w-full pl-5">
        {/* ターン番号のゴースト数字。ヘッダーの№表示と同じ数字・同じフォント/極薄opacityの
            組み合わせを使い回すことで、ヘッダーとメッセージリストが1つの体系だと分かるようにする */}
        {turnIndex !== undefined && (
          <span
            aria-hidden="true"
            className="pointer-events-none absolute -top-4 -left-2 -z-10 select-none font-[family-name:var(--font-syne)] text-[7rem] font-extrabold leading-none tracking-tighter text-white/[0.03]"
          >
            {String(turnIndex).padStart(2, "0")}
          </span>
        )}

        {/* 志粋が話していることを一目で示す、脊柱状のグラデーション罫線 */}
        <div
          className="absolute inset-y-0 left-0 w-0.5"
          style={{ background: "var(--gradient-shisui)" }}
          aria-hidden="true"
        />

        <p className="font-[family-name:var(--font-syne)] text-[10px] font-bold uppercase tracking-[0.3em] text-white/30">
          志粋
        </p>

        {/* 送信直後、thinking/contentのどちらもまだ届いていない空白期間は
            「思考中...」という静的なラベルだけを見せる(ヘッダーの「応答中」パルスが
            生存確認の役割を兼ねるため、ここに専用のパルス演出は置かない)。 */}
        {isStreamingNow && !message.thinking && !message.content && (
          <p className="mt-1 font-mono text-[10px] tracking-wider text-white/25">思考中...</p>
        )}

        <AnimatePresence>
          {isStreamingNow && message.thinking && (
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

        <MarkdownContent content={message.content} className="text-white/60" />

        {isStreamingNow && message.content && (
          <motion.span
            className="ml-0.5 inline-block h-[1em] w-[0.5em] translate-y-[0.15em] bg-[#b8935a] align-middle"
            initial={{ opacity: 0.25 }}
            animate={{ opacity: [0.25, 1, 0.25] }}
            transition={{ duration: 1.2, repeat: Infinity, ease: "easeInOut" }}
            aria-hidden="true"
          />
        )}
        {isStreamingNow && message._toolStatus && (
          <div className="mt-1 flex flex-col gap-1">
            <p className="font-mono text-[10px] uppercase tracking-wider text-[#b8935a]/80">
              {message._toolStatus}
            </p>
            <div className="h-px w-16 bg-[#b8935a]/20">
              <motion.div
                className="h-px bg-[#b8935a]"
                animate={{ width: ["10%", "90%", "10%"] }}
                transition={{ duration: 1.2, repeat: Infinity, ease: "easeInOut" }}
              />
            </div>
          </div>
        )}
      </div>
    </motion.div>
  )
}
