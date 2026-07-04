"use client"

import { useEffect, useRef, useState, type KeyboardEvent } from "react"
import { motion } from "framer-motion"
import { cn } from "@/lib/utils"
import { EASE } from "@/lib/motion"

interface FloatingInputProps {
  onSend: (message: string) => void
  disabled?: boolean
  autoFocus?: boolean
}

/**
 * 画面下部に1本の線だけ見える、極限までフラットな入力欄。
 */
export function FloatingInput({ onSend, disabled, autoFocus }: FloatingInputProps) {
  const [value, setValue] = useState("")
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (autoFocus) {
      textareaRef.current?.focus()
    }
  }, [autoFocus])

  const handleSend = () => {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setValue("")
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    // IME変換確定のEnter(isComposing、またはIME経由の場合keyCode 229)は送信としない。
    // これを見ないと、日本語入力中に変換確定しただけでメッセージが送信されてしまう。
    if (event.nativeEvent.isComposing || event.keyCode === 229) {
      return
    }
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault()
      handleSend()
    }
  }

  const canSend = !disabled && value.trim().length > 0

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
            placeholder="志粋にメッセージを送る..."
            disabled={disabled}
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
        </div>
      </div>
    </motion.div>
  )
}
