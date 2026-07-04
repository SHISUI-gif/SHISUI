"use client"

import { useEffect, useRef, useState, type KeyboardEvent } from "react"
import { motion } from "framer-motion"
import { cn } from "@/lib/utils"
import { EASE } from "@/lib/motion"

interface FloatingInputProps {
  onSend: (message: string) => void
  onStop?: () => void
  isStreaming?: boolean
  autoFocus?: boolean
}

/**
 * 画面下部に1本の線だけ見える、極限までフラットな入力欄。
 *
 * Enterは改行(通常のテキストエリアと同じ挙動)。送信はCmd/Ctrl+Enterか
 * Sendボタンのみ — 誤って送信してしまう事故を減らすため、あえて
 * 「Enterで即送信」にはしていない。
 */
export function FloatingInput({ onSend, onStop, isStreaming, autoFocus }: FloatingInputProps) {
  const [value, setValue] = useState("")
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (autoFocus) {
      textareaRef.current?.focus()
    }
  }, [autoFocus])

  const handleSend = () => {
    const trimmed = value.trim()
    if (!trimmed || isStreaming) return
    onSend(trimmed)
    setValue("")
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    // IME変換確定のEnter(isComposing、またはIME経由の場合keyCode 229)はここでは無視。
    if (event.nativeEvent.isComposing || event.keyCode === 229) {
      return
    }
    if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
      event.preventDefault()
      handleSend()
    }
    // 通常のEnter(修飾キーなし)は改行として素通しする(送信しない)
  }

  const canSend = !isStreaming && value.trim().length > 0

  return (
    <motion.div
      className="sticky bottom-0 w-full px-6 pb-10 pt-4 bg-black"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.7, ease: EASE, delay: 0.2 }}
    >
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-3">
        <div className="flex items-baseline gap-6 border-b border-white/15 pb-2">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="志粋にメッセージを送る... (Cmd/Ctrl+Enterで送信)"
            disabled={isStreaming}
            rows={1}
            className={cn(
              "field-sizing-content min-h-0 flex-1 resize-none bg-transparent border-none outline-none",
              // iOS Safariはinput/textareaのフォントサイズが16px未満だとフォーカス時に
              // 自動でズームインしてしまうため、スマホ幅ではtext-base(16px)を使う
              "px-0 py-0 text-base leading-relaxed text-white/90 sm:text-sm",
              "placeholder:text-white/25 placeholder:font-mono placeholder:text-xs placeholder:tracking-wider",
              "focus:outline-none focus-visible:outline-none focus-visible:ring-0",
              "disabled:cursor-not-allowed disabled:opacity-30",
            )}
          />
          {isStreaming ? (
            <button
              type="button"
              onClick={onStop}
              className={cn(
                "shrink-0 bg-transparent border-none outline-none cursor-pointer",
                "font-mono text-[10px] tracking-[0.25em] text-[#c8ff00]/70 uppercase",
                "transition-colors hover:text-[#c8ff00]",
                "focus-visible:outline-none",
              )}
            >
              Stop
            </button>
          ) : (
            <button
              type="button"
              onClick={handleSend}
              disabled={!canSend}
              className={cn(
                "shrink-0 bg-transparent border-none outline-none cursor-pointer",
                "font-mono text-[10px] tracking-[0.25em] text-white/30 uppercase",
                "transition-colors hover:text-[#c8ff00]",
                "focus-visible:outline-none disabled:pointer-events-none disabled:opacity-0",
              )}
            >
              Send
            </button>
          )}
        </div>
      </div>
    </motion.div>
  )
}
