"use client"

import { useEffect, useRef, useState, type ChangeEvent, type KeyboardEvent } from "react"
import { motion } from "framer-motion"
import { cn } from "@/lib/utils"
import { EASE } from "@/lib/motion"

interface FloatingInputProps {
  onSend: (message: string) => void
  onStop?: () => void
  isStreaming?: boolean
  autoFocus?: boolean
}

interface AttachedFile {
  name: string
  content: string
}

// 添付を許可する拡張子。画像・PDF等のバイナリはreadAsText()で文字化けするため、
// 現在のモデル(qwen2.5/qwen3系、いずれもvision非対応)で意味のある
// テキスト・コードファイルのみに絞る。画像対応は別途visionモデル導入が必要。
const ACCEPTED_FILE_EXTENSIONS =
  ".txt,.md,.py,.js,.jsx,.ts,.tsx,.json,.csv,.log,.yaml,.yml,.html,.css,.sh,.rb,.go,.rs,.java,.c,.cpp,.h"
const MAX_FILE_CHARS = 50_000

// SpeechRecognitionは標準化前のベンダープレフィックス付きAPIのため、
// TypeScriptの標準libには型定義が無い。存在チェックのみ行う。
type SpeechRecognitionLike = {
  lang: string
  interimResults: boolean
  continuous: boolean
  onresult: ((event: unknown) => void) | null
  onend: (() => void) | null
  onerror: (() => void) | null
  start: () => void
  stop: () => void
}

function getSpeechRecognitionCtor(): (new () => SpeechRecognitionLike) | undefined {
  if (typeof window === "undefined") return undefined
  const w = window as unknown as {
    SpeechRecognition?: new () => SpeechRecognitionLike
    webkitSpeechRecognition?: new () => SpeechRecognitionLike
  }
  return w.SpeechRecognition ?? w.webkitSpeechRecognition
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
  const [attachedFile, setAttachedFile] = useState<AttachedFile | null>(null)
  const [fileError, setFileError] = useState<string | null>(null)
  const [isListening, setIsListening] = useState(false)
  const [speechSupported, setSpeechSupported] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null)

  useEffect(() => {
    if (autoFocus) {
      textareaRef.current?.focus()
    }
  }, [autoFocus])

  useEffect(() => {
    setSpeechSupported(getSpeechRecognitionCtor() !== undefined)
  }, [])

  const handleSend = () => {
    const trimmed = value.trim()
    if ((!trimmed && !attachedFile) || isStreaming) return

    const message = attachedFile
      ? `以下のファイルの内容:\n<file name="${attachedFile.name}">\n${attachedFile.content}\n</file>\n\n${trimmed}`
      : trimmed

    onSend(message)
    setValue("")
    setAttachedFile(null)
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

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = "" // 同じファイルを連続選択しても onChange が発火するようにする
    if (!file) return

    setFileError(null)
    const reader = new FileReader()
    reader.onload = () => {
      const text = typeof reader.result === "string" ? reader.result : ""
      if (text.length > MAX_FILE_CHARS) {
        setFileError(`ファイルが大きすぎます(${MAX_FILE_CHARS.toLocaleString()}文字まで)`)
        return
      }
      setAttachedFile({ name: file.name, content: text })
    }
    reader.onerror = () => setFileError("ファイルを読み込めませんでした")
    reader.readAsText(file)
  }

  const toggleListening = () => {
    if (isListening) {
      recognitionRef.current?.stop()
      return
    }

    const Ctor = getSpeechRecognitionCtor()
    if (!Ctor) return

    const recognition = new Ctor()
    recognition.lang = "ja-JP"
    recognition.interimResults = false
    recognition.continuous = false
    recognition.onresult = (event) => {
      const results = (event as { results: ArrayLike<{ 0: { transcript: string } }> }).results
      const transcript = Array.from(results)
        .map((result) => result[0].transcript)
        .join("")
      setValue((prev) => (prev ? `${prev}${transcript}` : transcript))
    }
    recognition.onend = () => setIsListening(false)
    recognition.onerror = () => setIsListening(false)

    recognitionRef.current = recognition
    setIsListening(true)
    recognition.start()
  }

  const canSend = !isStreaming && (value.trim().length > 0 || attachedFile !== null)

  return (
    <motion.div
      className="sticky bottom-0 w-full px-6 pb-10 pt-4 bg-black"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.7, ease: EASE, delay: 0.2 }}
    >
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-2">
        {(attachedFile || fileError) && (
          <div className="flex items-center gap-2 font-mono text-[10px] text-white/40">
            {attachedFile && (
              <span className="flex items-center gap-2 border border-white/15 px-2 py-1">
                {attachedFile.name}
                <button
                  type="button"
                  onClick={() => setAttachedFile(null)}
                  className="text-white/40 hover:text-[#c8ff00]"
                  aria-label="添付を取り消す"
                >
                  ×
                </button>
              </span>
            )}
            {fileError && <span className="text-red-400">{fileError}</span>}
          </div>
        )}

        <div className="flex items-baseline gap-4 border-b border-white/15 pb-2">
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPTED_FILE_EXTENSIONS}
            onChange={handleFileChange}
            className="hidden"
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={isStreaming}
            aria-label="ファイルを添付"
            className={cn(
              "shrink-0 bg-transparent border-none outline-none cursor-pointer",
              "font-mono text-base text-white/30 leading-none",
              "transition-colors hover:text-[#c8ff00]",
              "disabled:pointer-events-none disabled:opacity-20",
            )}
          >
            +
          </button>

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

          {speechSupported && (
            <button
              type="button"
              onClick={toggleListening}
              disabled={isStreaming}
              aria-label={isListening ? "音声入力を停止" : "音声入力を開始"}
              className={cn(
                "shrink-0 bg-transparent border-none outline-none cursor-pointer",
                "font-mono text-[10px] tracking-[0.25em] uppercase",
                isListening ? "text-[#c8ff00] animate-pulse" : "text-white/30",
                "transition-colors hover:text-[#c8ff00]",
                "disabled:pointer-events-none disabled:opacity-20",
              )}
            >
              Mic
            </button>
          )}

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
