"use client"

import { useEffect, useRef, useState } from "react"
import { AnimatePresence, motion } from "framer-motion"
import { AvatarDisplay } from "@/components/AvatarDisplay"
import { LocalClock } from "@/components/LocalClock"
import { LoginForm } from "@/components/auth/LoginForm"
import { ActivityLog } from "@/components/chat/ActivityLog"
import { ChatMessages } from "@/components/chat/ChatMessages"
import { EvolutionProposals } from "@/components/chat/EvolutionProposals"
import { FeedbackForm } from "@/components/chat/FeedbackForm"
import { FeedbackReview } from "@/components/chat/FeedbackReview"
import { FloatingInput } from "@/components/chat/FloatingInput"
import { Sidebar } from "@/components/chat/Sidebar"
import { StartupLoader } from "@/components/StartupLoader"
import { LiquidChrome } from "@/components/three/LiquidChrome"
import { clearAuth, loadAuth, saveAuth, getCurrentUser } from "@/lib/auth"
import { AuthError, fetchProactiveCheckin, streamChat } from "@/lib/api"
import { getRecentActivity, getSleepStatus } from "@/lib/activity"
import { getAvatarState } from "@/lib/avatar"
import { deleteConversation, getConversationMessages, listConversations } from "@/lib/conversations"
import { applyProposal, getPendingProposals, rejectProposal } from "@/lib/evolution"
import { dismissFeedback, getAllFeedback, submitFeedback } from "@/lib/userFeedback"
import { cn } from "@/lib/utils"
import type {
  ActivityEntry,
  AuthUser,
  AvatarItem,
  ChatMessage,
  Conversation,
  CurrentUser,
  EvolutionProposal,
  UserFeedbackEntry,
} from "@/lib/types"
import { EASE, SPRING } from "@/lib/motion"

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
  layoutId,
}: {
  text: string
  className?: string
  ready: boolean
  layoutId?: string
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
      layoutId={layoutId}
      transition={layoutId ? SPRING : undefined}
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

// ヒーロー画面の統計(会話数・解除数・ムード)はサイドバーに移した
// (「情報より志粋の存在感を優先する没入型の1枚絵」という方針のため)。

// チャット開始時の候補プロンプト。実際に志粋が対応できる機能だけを挙げる
// (架空の技術的読み取り値やこのセッション固有の開発内容は含めない)。
const SUGGESTED_PROMPTS = [
  "今日の天気を教えて",
  "最近の夜間修行で何を学んだか教えて",
  "コードのレビューをお願いしたい",
  "最近あった出来事について話を聞いてほしい",
]

// チャット画面を開いたまま何もやり取りが無い状態がこの時間続いたら、志粋から
// 自然に一言話しかける(プロアクティブな話しかけ)。
const PROACTIVE_CHECKIN_IDLE_MS = 1 * 60 * 1000
// 上記の判定自体は軽い処理だが、setIntervalで秒単位の無駄なre-renderを避けるための巡回間隔。
// IDLE_MSが短いので、判定の粒度もそれに合わせて詰める
const PROACTIVE_CHECKIN_POLL_MS = 10 * 1000
// 睡眠モードが今夜始まったことがその場で分かるように、ヘッダーに軽く表示するための
// ポーリング間隔。睡眠サイクル自体は数分かかりうる処理なので、秒単位で追う必要は無い。
const SLEEP_STATUS_POLL_MS = 60 * 1000

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
  const [mood, setMood] = useState<string | null>(null)
  const [activityLogOpen, setActivityLogOpen] = useState(false)
  const [activities, setActivities] = useState<ActivityEntry[]>([])
  const [sleepInProgress, setSleepInProgress] = useState(false)
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null)
  const [evolutionOpen, setEvolutionOpen] = useState(false)
  const [proposals, setProposals] = useState<EvolutionProposal[]>([])
  const [feedbackFormOpen, setFeedbackFormOpen] = useState(false)
  const [feedbackReviewOpen, setFeedbackReviewOpen] = useState(false)
  const [feedbackEntries, setFeedbackEntries] = useState<UserFeedbackEntry[]>([])
  const [ready, setReady] = useState(false)
  // 生成中でも次のメッセージを送れるようにするため、単一のAbortController
  // ではなく「今動いている全リクエスト」をSetで管理する。Stopは動いている
  // 全部を一括で中断する(個別の吹き出しごとの停止ボタンは持たない設計)。
  const activeControllersRef = useRef<Set<AbortController>>(new Set())
  const nextLocalIdRef = useRef(0)
  const conversationIdRef = useRef<number | null>(null)
  // プロアクティブな話しかけ用: 最後にやり取り(送信/受信)があった時刻。
  // 話しかけた直後もここを更新することで、そのまま連続で何度も話しかけ続けるのを防ぐ。
  const lastActivityAtRef = useRef(Date.now())
  const proactiveCheckinInFlightRef = useRef(false)
  // setIntervalのコールバックは古いクロージャの値を見てしまうため、判定に必要な
  // 最新のstateを都度この参照にミラーしておく(intervalそのものは1回だけ張って、
  // 依存配列の変化のたびに再生成・巻き戻ることが無いようにするため)
  const latestChatStateRef = useRef({
    chatOpen: false,
    conversationId: null as number | null,
    streamingCount: 0,
    hasMessages: false,
    token: null as string | null,
  })

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
      .then((state) => {
        setAvatarItems(state.unlockedItems)
        setMood(state.mood)
      })
      .catch((error) => {
        if (error instanceof AuthError) handleLogout()
      })
  }, [user])

  useEffect(() => {
    if (!user) return
    getCurrentUser(user.token)
      .then(setCurrentUser)
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
    setCurrentUser(null)
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

  const handleOpenEvolutionProposals = async () => {
    if (!user) return
    try {
      setProposals(await getPendingProposals(user.token))
      setEvolutionOpen(true)
    } catch (error) {
      if (error instanceof AuthError) handleLogout()
    }
  }

  const handleApplyProposal = async (id: string) => {
    if (!user) return
    try {
      await applyProposal(user.token, id)
      setProposals((prev) => prev.filter((p) => p.id !== id))
    } catch (error) {
      if (error instanceof AuthError) handleLogout()
    }
  }

  const handleRejectProposal = async (id: string) => {
    if (!user) return
    try {
      await rejectProposal(user.token, id)
      setProposals((prev) => prev.filter((p) => p.id !== id))
    } catch (error) {
      if (error instanceof AuthError) handleLogout()
    }
  }

  const handleSubmitFeedback = async (content: string) => {
    if (!user) return
    try {
      await submitFeedback(user.token, content)
    } catch (error) {
      if (error instanceof AuthError) handleLogout()
    }
  }

  const handleOpenFeedbackReview = async () => {
    if (!user) return
    try {
      setFeedbackEntries(await getAllFeedback(user.token))
      setFeedbackReviewOpen(true)
    } catch (error) {
      if (error instanceof AuthError) handleLogout()
    }
  }

  const handleDismissFeedback = async (id: string) => {
    if (!user) return
    try {
      await dismissFeedback(user.token, id)
      setFeedbackEntries((prev) =>
        prev.map((entry) => (entry.id === id ? { ...entry, reviewed: true } : entry)),
      )
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

  const handleDeleteConversation = async (id: number) => {
    if (!user) return
    try {
      const ok = await deleteConversation(user.token, id)
      if (!ok) return
      setConversationList((prev) => prev.filter((c) => c.id !== id))
      // 今開いている会話を消した場合は、真っさらな新規会話の状態に戻す
      // (削除したはずの会話がそのまま表示され続けるのを防ぐため)
      if (conversationIdRef.current === id) {
        handleNewConversation()
      }
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
    lastActivityAtRef.current = Date.now()

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
      lastActivityAtRef.current = Date.now()
    }
  }

  const hasMessages = messages.length > 0

  // 毎レンダー後にlatestChatStateRefを最新化するだけの軽い同期(依存配列を
  // 持たせて頻繁にintervalそのものを張り直すのではなく、intervalは1本だけ
  // 張ったままにして、判定に使う値だけをここで都度書き換える)
  useEffect(() => {
    latestChatStateRef.current = {
      chatOpen,
      conversationId,
      streamingCount,
      hasMessages,
      token: user?.token ?? null,
    }
  })

  // チャット画面を開いたまま数分間やり取りが無ければ、志粋から自然に話しかける
  useEffect(() => {
    const intervalId = setInterval(() => {
      const { chatOpen, conversationId, streamingCount, hasMessages, token } =
        latestChatStateRef.current
      if (!chatOpen || !hasMessages || !conversationId || streamingCount > 0 || !token) return
      if (document.visibilityState !== "visible") return
      if (Date.now() - lastActivityAtRef.current < PROACTIVE_CHECKIN_IDLE_MS) return
      if (proactiveCheckinInFlightRef.current) return

      proactiveCheckinInFlightRef.current = true
      fetchProactiveCheckin(token, conversationId)
        .then((content) => {
          // ローカルLLMがまれに空応答を返すことがあるため、nullの場合は
          // 空の吹き出しを追加せず、この回は静かにスキップする
          if (!content) return
          setMessages((prev) => [...prev, { role: "assistant", content }])
          lastActivityAtRef.current = Date.now()
        })
        .catch(() => {
          // 取得できなくても静かに諦める(背後の軽い気配りなので、エラーを表に
          // 出してユーザーの操作を止めるほどのものではない)
        })
        .finally(() => {
          proactiveCheckinInFlightRef.current = false
        })
    }, PROACTIVE_CHECKIN_POLL_MS)

    return () => clearInterval(intervalId)
  }, [])

  // 睡眠モードが今夜始まったことがその場で分かるよう、ログイン中は定期的に
  // 実行中フラグをポーリングし、ヘッダーの表示に反映する。
  useEffect(() => {
    const token = user?.token
    if (!token) return

    const poll = () => {
      getSleepStatus(token)
        .then(setSleepInProgress)
        .catch(() => {})
    }
    poll()
    const intervalId = setInterval(poll, SLEEP_STATUS_POLL_MS)
    return () => clearInterval(intervalId)
  }, [user?.token])

  if (!authChecked) {
    return <div className="min-h-screen bg-black" />
  }

  if (!user) {
    return <LoginForm onAuthenticated={handleAuthenticated} />
  }

  return (
    <div
      className={cn(
        "relative flex min-h-screen flex-col bg-black",
        !chatOpen && "overflow-hidden",
      )}
    >
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
            className="relative flex min-h-screen flex-col overflow-hidden"
            exit={{ opacity: 0, scale: 0.96 }}
            transition={{ duration: 0.7, ease: EASE }}
          >
            {/* 志粋という存在そのものを見せる、没入感のある1枚絵として再構成。
                人物写真は「違和感がある」との指摘を受けて外し、リキッドクロームの
                ブロブ自体を主役の被写体にした。反射に使うライトも、写真の
                ランダムな都市風景(Environment preset)ではなく、サイト自体の
                アクセントカラー(アンバー+ダークブルー)に統一し、世界観を合わせている */}
            <div className="absolute inset-0 bg-black" />

            {/* 被写体(リキッドクローム)を囲む、ゆっくり回転する円環(参考UIのリング装飾)。
                高さ基準の%指定のため、縦長のスマホ画面だと横幅からはみ出す
                (画面幅375pxに対しh-[52%]は800px超の高さの52%=400px超になる)。
                スマホでは小さめの比率に落とす */}
            <motion.div
              aria-hidden="true"
              className="pointer-events-none absolute left-1/2 top-[46%] z-10 aspect-square h-[34%] -translate-x-1/2 -translate-y-1/2 rounded-full border border-white/20 sm:h-[52%]"
              animate={{ rotate: 360 }}
              transition={{ duration: 50, repeat: Infinity, ease: "linear" }}
            />

            {/* リキッドクローム — 人物の代わりにこれ自体を中央の主役にする */}
            <LiquidChrome className="left-1/2 top-[46%] z-[5] h-64 w-64 -translate-x-1/2 -translate-y-1/2 sm:h-96 sm:w-96" />

            {/* 中央だけだと周りの黒い空間が寂しいとの指摘を受け、同じ液体金属の
                質感の小さめのブロブを2つ散りばめる(ワイヤーフレーム等の別の
                ビジュアル言語は混ぜず、液体金属で統一する)。スマホでは
                余白が少なく窮屈になるため非表示にする */}
            <LiquidChrome className="left-[12%] top-[20%] z-[5] hidden h-24 w-24 sm:block" />
            <LiquidChrome className="right-[14%] top-[72%] z-[5] hidden h-20 w-20 sm:block" />

            {/* 1. 最小限のマストヘッド — 箱で囲わず、コーナーに文字だけ置く */}
            <motion.div
              className="relative z-10 flex items-center justify-between px-6 pt-6 sm:px-10 sm:pt-8 lg:px-16"
              initial={ready ? { opacity: 0, y: -12 } : false}
              animate={ready ? { opacity: 1, y: 0 } : undefined}
              transition={{ duration: 0.6, ease: EASE, delay: 0.1 }}
            >
              <span className="font-mono text-[10px] tracking-[0.35em] text-white/50 uppercase">
                志粋 / SHISUI
              </span>
              <LocalClock />
            </motion.div>

            {/* 2. 見出し — 中央上部。幾何学的でSF感の強いOrbitronに、
                アンバーのグロー(text-shadow)を added して「かっこよさ」を強調 */}
            <div className="relative z-10 flex justify-center pt-8 sm:pt-12">
              <h1
                className="text-center font-[family-name:var(--font-orbitron)] text-[clamp(2.5rem,9vw,5.5rem)] font-black tracking-[0.15em] text-white"
                style={{ textShadow: "0 0 40px rgba(184,147,90,0.5), 0 0 80px rgba(184,147,90,0.25)" }}
              >
                <StaggeredText text="SHISUI" ready={ready} />
              </h1>
            </div>

            {/* 4. 下部 — 挨拶キャプション+対話開始(参考UIの下部キャプションと同じ配置) */}
            <div className="relative z-10 mt-auto flex flex-col items-center gap-6 px-6 pb-10 text-center sm:pb-14">
              <div className="overflow-hidden">
                <motion.p
                  className="max-w-sm font-mono text-xs leading-relaxed text-white/60 sm:text-sm"
                  initial={ready ? { y: "100%", opacity: 0 } : false}
                  animate={ready ? { y: "0%", opacity: 1 } : undefined}
                  transition={{ duration: 0.8, ease: EASE, delay: 0.9 }}
                >
                  {user.name}さん、今日は何を話そうか?
                </motion.p>
              </div>
              <motion.button
                type="button"
                onClick={() => setChatOpen(true)}
                className="cursor-pointer rounded-full border border-white/25 px-8 py-3 font-mono text-[10px] uppercase tracking-[0.3em] text-white/80 outline-none transition-colors hover:border-white/60 hover:text-white"
                initial={ready ? { opacity: 0, y: 12 } : false}
                animate={ready ? { opacity: 1, y: 0 } : undefined}
                transition={{ duration: 0.8, ease: EASE, delay: 1.05 }}
                whileTap={{ scale: 0.96, transition: SPRING }}
              >
                対話を開始
              </motion.button>
            </div>
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
              isOwner={currentUser?.isOwner ?? false}
              sessionCount={conversationList.length}
              unlockCount={avatarItems.length}
              mood={mood}
              conversations={conversationList}
              activeConversationId={conversationId}
              onSelectConversation={handleSelectConversation}
              onDeleteConversation={handleDeleteConversation}
              onNewConversation={handleNewConversation}
              onOpenActivityLog={handleOpenActivityLog}
              onOpenEvolutionProposals={handleOpenEvolutionProposals}
              onOpenFeedbackForm={() => setFeedbackFormOpen(true)}
              onOpenFeedbackReview={handleOpenFeedbackReview}
              onLogout={handleLogout}
            />
            <ActivityLog
              isOpen={activityLogOpen}
              onClose={() => setActivityLogOpen(false)}
              activities={activities}
            />
            <EvolutionProposals
              isOpen={evolutionOpen}
              onClose={() => setEvolutionOpen(false)}
              proposals={proposals}
              onApply={handleApplyProposal}
              onReject={handleRejectProposal}
            />
            <FeedbackForm
              isOpen={feedbackFormOpen}
              onClose={() => setFeedbackFormOpen(false)}
              onSubmit={handleSubmitFeedback}
            />
            <FeedbackReview
              isOpen={feedbackReviewOpen}
              onClose={() => setFeedbackReviewOpen(false)}
              entries={feedbackEntries}
              onDismiss={handleDismissFeedback}
            />

            <motion.header
              className="sticky top-4 z-30 mx-4 flex h-14 shrink-0 overflow-hidden rounded-2xl border border-white/10 bg-white/[0.04] shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] backdrop-blur-xl sm:mx-8"
              initial={{ opacity: 0, y: -16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, ease: EASE, delay: 0.1 }}
            >
              <motion.button
                type="button"
                onClick={() => setSidebarOpen(true)}
                aria-label="会話履歴を開く"
                whileHover={{ scale: 1.08 }}
                whileTap={{ scale: 0.92 }}
                transition={SPRING}
                className="group flex w-14 shrink-0 flex-col items-center justify-center gap-1.5 border-r border-white/10"
              >
                <span className="block h-px w-5 bg-white/50 transition-colors group-hover:bg-[#b8935a]" />
                <span className="block h-px w-5 bg-white/50 transition-colors group-hover:bg-[#b8935a]" />
                <span className="block h-px w-5 bg-white/50 transition-colors group-hover:bg-[#b8935a]" />
              </motion.button>

              <div className="flex min-w-0 flex-1 items-center justify-between px-4">
                <p className="font-[family-name:var(--font-syne)] text-sm font-bold tracking-tight text-white">
                  SHISUI
                </p>
                <span className="font-mono text-[10px] tracking-[0.2em] text-white/25 tabular-nums">
                  {streamingCount > 0 ? (
                    <motion.span
                      className="text-[#b8935a]"
                      animate={{ opacity: [0.4, 1, 0.4] }}
                      transition={{ duration: 1.2, repeat: Infinity, ease: "easeInOut" }}
                    >
                      応答中
                    </motion.span>
                  ) : sleepInProgress ? (
                    <motion.span
                      className="text-[#b8935a]"
                      animate={{ opacity: [0.4, 1, 0.4] }}
                      transition={{ duration: 1.2, repeat: Infinity, ease: "easeInOut" }}
                    >
                      😴 睡眠学習中
                    </motion.span>
                  ) : (
                    `№ ${String(Math.ceil(messages.length / 2)).padStart(2, "0")}`
                  )}
                </span>
              </div>

              <motion.button
                type="button"
                onClick={() => setChatOpen(false)}
                aria-label="ホームに戻る"
                whileHover={{ scale: 1.08 }}
                whileTap={{ scale: 0.92 }}
                transition={SPRING}
                className="flex w-14 shrink-0 items-center justify-center border-l border-white/10 font-mono text-[10px] uppercase tracking-widest text-white/40 transition-colors hover:text-[#b8935a]"
              >
                ホーム
              </motion.button>
            </motion.header>

            {hasMessages && <ChatMessages messages={messages} />}

            {!hasMessages && (
              <div className="flex flex-1 flex-col items-center justify-center gap-6 px-6">
                <div className="h-32 w-32 opacity-70 sm:h-40 sm:w-40">
                  <AvatarDisplay unlockedItems={avatarItems} mood={mood} />
                </div>
                <p className="text-center font-[family-name:var(--font-syne)] text-xl font-light text-white sm:text-2xl">
                  {user.name}さん、何を話そうか?
                </p>

                {/* 候補プロンプト — 実際に使える機能に対応したものだけを提示する
                    (架空の技術的な読み取り値は表示しない)。クリックで即送信。
                    枠が単なる細線の四角で安っぽいとの指摘を受け、他画面と揃えた
                    ガラス質のカード(角丸・ぼかし・内側ハイライト)に変更 */}
                <div className="flex w-full max-w-sm flex-col gap-2.5">
                  {SUGGESTED_PROMPTS.map((suggestion) => (
                    <motion.button
                      key={suggestion}
                      type="button"
                      onClick={() => handleSend(suggestion)}
                      whileHover={{ scale: 1.02, y: -1 }}
                      whileTap={{ scale: 0.98 }}
                      transition={SPRING}
                      className="group flex items-center justify-between gap-3 rounded-2xl border border-white/10 bg-white/[0.04] px-5 py-3.5 text-left shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] backdrop-blur-xl transition-colors hover:border-[#b8935a]/40 hover:bg-white/[0.06]"
                    >
                      <span className="font-mono text-xs text-white/60 transition-colors group-hover:text-white/90">
                        {suggestion}
                      </span>
                      <span className="font-mono text-xs text-white/20 transition-colors group-hover:text-[#b8935a]">
                        →
                      </span>
                    </motion.button>
                  ))}
                </div>
              </div>
            )}

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
