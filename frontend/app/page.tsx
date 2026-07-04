"use client"

import { useEffect, useState } from "react"
import { AnimatePresence, motion } from "framer-motion"
import { ChatMessages } from "@/components/chat/ChatMessages"
import { FloatingInput } from "@/components/chat/FloatingInput"
import { StartupLoader } from "@/components/StartupLoader"
import { AmbientBackground } from "@/components/three/AmbientBackground"
import { streamChat } from "@/lib/api"
import type { ChatMessage } from "@/lib/types"
import { EASE } from "@/lib/motion"

const staggerContainer = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.08, delayChildren: 0.15 },
  },
}

const fadeUp = {
  hidden: { opacity: 0, y: 48 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.9, ease: EASE },
  },
}

function StaggeredText({
  text,
  className,
  ready,
}: {
  text: string
  className?: string
  ready: boolean
}) {
  if (!ready) {
    return <span className={className}>{text}</span>
  }

  return (
    <motion.span
      className={className}
      variants={staggerContainer}
      initial="hidden"
      animate="visible"
      aria-label={text}
    >
      {text.split("").map((char, i) => (
        <motion.span
          key={`${char}-${i}`}
          variants={fadeUp}
          className="inline-block"
          aria-hidden="true"
        >
          {char === " " ? "\u00A0" : char}
        </motion.span>
      ))}
    </motion.span>
  )
}

export default function Home() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [toolStatus, setToolStatus] = useState<string | undefined>(undefined)
  const [chatOpen, setChatOpen] = useState(false)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    setReady(true)
  }, [])

  const handleSend = async (text: string) => {
    const userMessage: ChatMessage = { role: "user", content: text }
    setMessages((prev) => [...prev, userMessage, { role: "assistant", content: "", thinking: "" }])
    setIsStreaming(true)
    setToolStatus(undefined)

    try {
      for await (const event of streamChat(text, messages)) {
        if (event.type === "tool_status") {
          setToolStatus(event.text)
          continue
        }
        setToolStatus(undefined)
        setMessages((prev) => {
          const next = [...prev]
          const last = next[next.length - 1]
          if (event.type === "thinking") {
            next[next.length - 1] = { ...last, thinking: (last.thinking ?? "") + event.text }
          } else if (event.type === "content") {
            next[next.length - 1] = { ...last, content: last.content + event.text }
          }
          return next
        })
      }
    } catch (error) {
      setMessages((prev) => {
        const next = [...prev]
        next[next.length - 1] = {
          ...next[next.length - 1],
          content: `⚠️ エラーが発生しちゃった: ${(error as Error).message}`,
        }
        return next
      })
    } finally {
      setIsStreaming(false)
      setToolStatus(undefined)
    }
  }

  const hasMessages = messages.length > 0

  return (
    <div className="relative flex min-h-screen flex-col overflow-hidden bg-black">
      <StartupLoader />

      {/* subtle grid texture */}
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage:
            "linear-gradient(#fff 1px, transparent 1px), linear-gradient(90deg, #fff 1px, transparent 1px)",
          backgroundSize: "80px 80px",
        }}
        aria-hidden="true"
      />

      <AnimatePresence mode="wait">
        {!chatOpen ? (
          <motion.section
            key="hero"
            className="relative flex min-h-screen flex-col items-center justify-center px-6"
            exit={{ opacity: 0, scale: 0.96 }}
            transition={{ duration: 0.7, ease: EASE }}
          >
            {/* 常時ゆっくり動く3D背景。ヒーロー画面のみ、チャット画面には出さない */}
            <AmbientBackground />

            {/* ghost layer — extreme size contrast */}
            <motion.p
              className="pointer-events-none absolute top-[18%] left-1/2 -translate-x-1/2 font-[family-name:var(--font-syne)] text-[clamp(4rem,18vw,14rem)] font-extrabold leading-none tracking-[-0.06em] text-white/[0.04] select-none"
              initial={ready ? { opacity: 0, y: 80 } : false}
              animate={ready ? { opacity: 1, y: 0 } : undefined}
              transition={{ duration: 1.2, ease: EASE, delay: 0.1 }}
              aria-hidden="true"
            >
              志粋
            </motion.p>

            <div className="relative z-10 w-full max-w-[100vw] text-center">
              <h1 className="font-[family-name:var(--font-syne)] text-[clamp(3.5rem,14vw,11rem)] font-extrabold leading-[0.82] tracking-[-0.05em] text-white">
                <StaggeredText text="SHISUI" ready={ready} />
              </h1>

              <motion.div
                className="relative mt-4"
                variants={staggerContainer}
                initial={ready ? "hidden" : false}
                animate={ready ? "visible" : undefined}
              >
                <motion.p
                  variants={fadeUp}
                  className="font-mono text-[clamp(0.65rem,1.8vw,0.875rem)] tracking-[0.45em] text-[#c8ff00] uppercase sm:absolute sm:-bottom-3 sm:right-0 sm:translate-x-1/4"
                >
                  Autonomous AI
                </motion.p>
                <motion.p
                  variants={fadeUp}
                  className="mt-6 font-mono text-[clamp(0.6rem,1.2vw,0.75rem)] tracking-[0.25em] text-white/30 uppercase"
                >
                  Local · Private · Autonomous
                </motion.p>
              </motion.div>
            </div>

            {/* overlapping accent word */}
            <motion.span
              className="pointer-events-none absolute bottom-[38%] right-[8%] font-[family-name:var(--font-syne)] text-[clamp(2rem,6vw,5rem)] font-bold leading-none tracking-tight text-[#c8ff00]/20 select-none sm:right-[15%]"
              initial={ready ? { opacity: 0, x: 40 } : false}
              animate={ready ? { opacity: 1, x: 0 } : undefined}
              transition={{ duration: 1, ease: EASE, delay: 0.6 }}
              aria-hidden="true"
            >
              AI
            </motion.span>

            <motion.button
              type="button"
              onClick={() => setChatOpen(true)}
              className="absolute bottom-12 left-1/2 -translate-x-1/2 bg-transparent border-none outline-none cursor-pointer"
              initial={ready ? { opacity: 0, y: 24 } : false}
              animate={ready ? { opacity: 1, y: 0 } : undefined}
              transition={{ duration: 0.8, ease: EASE, delay: 1.1 }}
              whileHover={{ color: "#c8ff00" }}
            >
              <span className="font-mono text-xs tracking-[0.35em] text-white/50 uppercase transition-colors hover:text-[#c8ff00]">
                対話を開始
              </span>
              <motion.span
                className="mt-3 block h-px w-16 bg-white/20 mx-auto"
                initial={ready ? { scaleX: 0 } : false}
                animate={ready ? { scaleX: 1 } : undefined}
                transition={{ duration: 0.6, ease: EASE, delay: 1.3 }}
              />
            </motion.button>
          </motion.section>
        ) : (
          <motion.div
            key="chat"
            className="flex min-h-screen flex-col"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.6, ease: EASE }}
          >
            <motion.header
              className="shrink-0 px-6 pt-8 pb-4"
              initial={{ opacity: 0, y: -16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, ease: EASE, delay: 0.1 }}
            >
              <p className="font-[family-name:var(--font-syne)] text-lg font-bold tracking-tight text-white">
                SHISUI
              </p>
              <motion.span
                className="mt-1 block h-px w-10 origin-left bg-[#c8ff00]"
                initial={{ scaleX: 0 }}
                animate={{ scaleX: 1 }}
                transition={{ duration: 0.5, ease: EASE, delay: 0.3 }}
              />
              <p className="mt-2 font-mono text-[10px] tracking-[0.3em] text-[#c8ff00]/70 uppercase">
                Autonomous AI
              </p>
            </motion.header>

            {hasMessages && (
              <ChatMessages messages={messages} toolStatus={toolStatus} isStreaming={isStreaming} />
            )}

            {!hasMessages && <div className="flex-1" />}

            <FloatingInput
              onSend={handleSend}
              disabled={isStreaming}
              autoFocus
            />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
