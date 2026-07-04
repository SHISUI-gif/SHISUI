"use client"

import { useEffect, useRef, useState, type TouchEvent, type WheelEvent } from "react"
import { AnimatePresence, motion } from "framer-motion"
import { AvatarDisplay } from "@/components/AvatarDisplay"
import { LoginForm } from "@/components/auth/LoginForm"
import { ActivityLog } from "@/components/chat/ActivityLog"
import { ChatMessages } from "@/components/chat/ChatMessages"
import { FloatingInput } from "@/components/chat/FloatingInput"
import { Sidebar } from "@/components/chat/Sidebar"
import { StartupLoader } from "@/components/StartupLoader"
import { AmbientBackground } from "@/components/three/AmbientBackground"
import { clearAuth, loadAuth, saveAuth } from "@/lib/auth"
import { AuthError, streamChat } from "@/lib/api"
import { getRecentActivity } from "@/lib/activity"
import { getAvatarState } from "@/lib/avatar"
import { getConversationMessages, listConversations } from "@/lib/conversations"
import type { ActivityEntry, AuthUser, AvatarItem, ChatMessage, Conversation } from "@/lib/types"
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
  const [user, setUser] = useState<AuthUser | null>(null)
  const [authChecked, setAuthChecked] = useState(false)
  const [conversationId, setConversationId] = useState<number | null>(null)
  const [conversationList, setConversationList] = useState<Conversation[]>([])
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [streamingCount, setStreamingCount] = useState(0)
  const [chatOpen, setChatOpen] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [avatarItems, setAvatarItems] = useState<AvatarItem[]>([])
  const [activityLogOpen, setActivityLogOpen] = useState(false)
  const [activities, setActivities] = useState<ActivityEntry[]>([])
  const [ready, setReady] = useState(false)
  // 生成中でも次のメッセージを送れるようにするため、単一のAbortController
  // ではなく「今動いている全リクエスト」をSetで管理する。Stopは動いている
  // 全部を一括で中断する(個別の吹き出しごとの停止ボタンは持たない設計)。
  const activeControllersRef = useRef<Set<AbortController>>(new Set())
  const nextLocalIdRef = useRef(0)
  const conversationIdRef = useRef<number | null>(null)
  const touchStartYRef = useRef<number | null>(null)

  // ヒーロー画面を上にスワイプ(スマホ)または上にスクロール(トラックパッド/ホイール)
  // するとチャットを開く。ボタンタップは引き続き従来通り使える。
  const SWIPE_UP_THRESHOLD_PX = 60

  const handleHeroTouchStart = (event: TouchEvent) => {
    touchStartYRef.current = event.touches[0]?.clientY ?? null
  }

  const handleHeroTouchEnd = (event: TouchEvent) => {
    const startY = touchStartYRef.current
    touchStartYRef.current = null
    if (startY === null) return
    const endY = event.changedTouches[0]?.clientY ?? startY
    if (startY - endY > SWIPE_UP_THRESHOLD_PX) {
      setChatOpen(true)
    }
  }

  const handleHeroWheel = (event: WheelEvent) => {
    if (event.deltaY < -20) {
      setChatOpen(true)
    }
  }

  useEffect(() => {
    setReady(true)
    const existing = loadAuth()
    if (existing) setUser(existing)
    setAuthChecked(true)
  }, [])

  useEffect(() => {
    if (user) refreshConversations(user.token)
  }, [user])

  useEffect(() => {
    if (!user) return
    getAvatarState(user.token)
      .then(setAvatarItems)
      .catch((error) => {
        if (error instanceof AuthError) handleLogout()
      })
  }, [user])

  const refreshConversations = async (token: string) => {
    try {
      setConversationList(await listConversations(token))
    } catch (error) {
      if (error instanceof AuthError) handleLogout()
    }
  }

  const handleAuthenticated = (authUser: AuthUser) => {
    saveAuth(authUser)
    setUser(authUser)
  }

  const handleLogout = () => {
    clearAuth()
    setUser(null)
    setChatOpen(false)
    conversationIdRef.current = null
    setConversationId(null)
    setConversationList([])
    setMessages([])
  }

  const handleNewConversation = () => {
    conversationIdRef.current = null
    setConversationId(null)
    setMessages([])
    setChatOpen(true)
  }

  const handleOpenActivityLog = async () => {
    if (!user) return
    try {
      setActivities(await getRecentActivity(user.token))
      setActivityLogOpen(true)
    } catch (error) {
      if (error instanceof AuthError) handleLogout()
    }
  }

  const handleSelectConversation = async (id: number) => {
    if (!user) return
    conversationIdRef.current = id
    setConversationId(id)
    try {
      setMessages(await getConversationMessages(user.token, id))
      setChatOpen(true)
    } catch (error) {
      if (error instanceof AuthError) handleLogout()
    }
  }

  const handleStop = () => {
    // 誤送信・送信取り消し用。今動いている全リクエストを中断する
    // (個別の吹き出しごとの停止は持たず、まとめて止める設計。それまでに
    // 届いていた内容はメッセージとしてそのまま残す)
    for (const controller of activeControllersRef.current) {
      controller.abort()
    }
  }

  const handleSend = async (text: string) => {
    if (!user) return
    // 生成中でも次のメッセージを送れるようにするため、「配列の最後の要素」ではなく
    // このメッセージ固有のlocalIdで吹き出しを識別する(複数のストリームが同時に
    // 走っていても、正しい吹き出しだけを更新できるようにするため)。
    const localId = nextLocalIdRef.current++
    const userMessage: ChatMessage = { role: "user", content: text }
    const assistantPlaceholder: ChatMessage = { role: "assistant", content: "", thinking: "", _localId: localId }
    setMessages((prev) => [...prev, userMessage, assistantPlaceholder])
    setStreamingCount((prev) => prev + 1)

    // 新規会話かどうかは、送信した瞬間のconversationIdRefで判定する(React stateの
    // 反映を待つとレースになるため)。ほぼ同時に2通「新規会話」を送った場合、
    // 2件目が1件目のconversation_id確定より先に評価されると別々の会話になって
    // しまう可能性はあるが、通常の人間の操作速度ではまず起きない
    const isNewConversation = conversationIdRef.current === null
    const requestConversationId = conversationIdRef.current
    const requestHistory = messages
    const controller = new AbortController()
    activeControllersRef.current.add(controller)

    try {
      for await (const event of streamChat(text, requestHistory, user.token, requestConversationId, controller.signal)) {
        if (conversationIdRef.current === null) {
          conversationIdRef.current = event.conversation_id
          setConversationId(event.conversation_id)
        }
        setMessages((prev) =>
          prev.map((m) => {
            if (m._localId !== localId) return m
            if (event.type === "tool_status") return { ...m, _toolStatus: event.text }
            if (event.type === "thinking") {
              return { ...m, thinking: (m.thinking ?? "") + event.text, _toolStatus: undefined }
            }
            if (event.type === "content") {
              return { ...m, content: m.content + event.text, _toolStatus: undefined }
            }
            return m
          }),
        )
      }
      // 新しい会話ならサイドバーの一覧に追加、既存の会話ならタイトルの
      // 更新日時が変わっているのでどちらの場合も一覧を再取得しておく
      if (isNewConversation) refreshConversations(user.token)
    } catch (error) {
      if (error instanceof AuthError) {
        // 生のHTTPエラーを見せて詰ませるのではなく、ログイン画面に戻して
        // すぐ再ログインできるようにする(セッション切れは日常的に起こりうる)
        handleLogout()
        return
      }
      if (error instanceof DOMException && error.name === "AbortError") {
        // 誤送信を止めた場合。エラーとしては見せず、それまで届いた分だけ残す
        // (何も届いていなければ空の吹き出しを消す)
        setMessages((prev) => {
          const target = prev.find((m) => m._localId === localId)
          if (target && target.role === "assistant" && !target.content && !target.thinking) {
            return prev.filter((m) => m._localId !== localId)
          }
          return prev
        })
        return
      }
      setMessages((prev) =>
        prev.map((m) =>
          m._localId === localId
            ? { ...m, content: `⚠️ エラーが発生しちゃった: ${(error as Error).message}` }
            : m,
        ),
      )
    } finally {
      activeControllersRef.current.delete(controller)
      setStreamingCount((prev) => prev - 1)
      // ストリーミング終了の目印として_localIdを外す(この値自体がChatMessages側の
      // 「このメッセージは今生成中か」の判定に使われている)
      setMessages((prev) =>
        prev.map((m) => (m._localId === localId ? { ...m, _localId: undefined } : m)),
      )
    }
  }

  const hasMessages = messages.length > 0

  if (!authChecked) {
    return <div className="min-h-screen bg-black" />
  }

  if (!user) {
    return <LoginForm onAuthenticated={handleAuthenticated} />
  }

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
            onTouchStart={handleHeroTouchStart}
            onTouchEnd={handleHeroTouchEnd}
            onWheel={handleHeroWheel}
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

            <div className="relative z-10 mt-8 flex flex-col items-center gap-4 px-6">
              <AvatarDisplay unlockedItems={avatarItems} />
              <motion.p
                className="text-center font-mono text-sm text-white/50 sm:text-base"
                initial={ready ? { opacity: 0, y: 16 } : false}
                animate={ready ? { opacity: 1, y: 0 } : undefined}
                transition={{ duration: 0.8, ease: EASE, delay: 0.9 }}
              >
                {user.name}さん、今日は何を話そうか?
              </motion.p>
            </div>

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
            <Sidebar
              isOpen={sidebarOpen}
              onClose={() => setSidebarOpen(false)}
              userName={user.name}
              conversations={conversationList}
              activeConversationId={conversationId}
              onSelectConversation={handleSelectConversation}
              onNewConversation={handleNewConversation}
              onOpenActivityLog={handleOpenActivityLog}
              onLogout={handleLogout}
            />
            <ActivityLog
              isOpen={activityLogOpen}
              onClose={() => setActivityLogOpen(false)}
              activities={activities}
            />

            <motion.header
              className="sticky top-0 z-30 shrink-0 bg-black px-6 pt-8 pb-4"
              initial={{ opacity: 0, y: -16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, ease: EASE, delay: 0.1 }}
            >
              <button
                type="button"
                onClick={() => setSidebarOpen(true)}
                aria-label="会話履歴を開く"
                className="group mb-3 flex flex-col gap-1.5 p-1 -m-1"
              >
                <span className="block h-px w-5 bg-white/50 transition-colors group-hover:bg-[#c8ff00]" />
                <span className="block h-px w-5 bg-white/50 transition-colors group-hover:bg-[#c8ff00]" />
                <span className="block h-px w-5 bg-white/50 transition-colors group-hover:bg-[#c8ff00]" />
              </button>
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

            {hasMessages && <ChatMessages messages={messages} />}

            {!hasMessages && <div className="flex-1" />}

            <FloatingInput
              onSend={handleSend}
              onStop={handleStop}
              isStreaming={streamingCount > 0}
              autoFocus
            />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
