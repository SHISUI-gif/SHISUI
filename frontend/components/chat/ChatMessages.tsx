import { useEffect, useRef } from "react"
import { ScrollArea } from "@/components/ui/scroll-area"
import type { ChatMessage as ChatMessageType } from "@/lib/types"
import { ChatMessage } from "./ChatMessage"

interface ChatMessagesProps {
  messages: ChatMessageType[]
}

interface Turn {
  user?: ChatMessageType
  assistant?: ChatMessageType
  index: number
}

/**
 * handleSend()はユーザー発言とアシスタントのプレースホルダーを必ず同時に
 * 配列へ追加し、履歴読み込み(getConversationMessages)も発言順を保つため、
 * 基本的にメッセージ配列は「ユーザー→アシスタント」のペア(1往復=1ターン)の
 * 並びになっている。ただし、数分間発言が無かった時に志粋から自然に話しかける
 * 「プロアクティブな一言」(app/page.tsxのproactive-checkinポーリング)は、
 * 対になるユーザー発言を持たないアシスタント単独のメッセージとして配列に
 * 追加されるため、role(user/assistant)を見て動的にペアリングする
 * (単純な2件ずつの決め打ちチャンクだと、この単独メッセージが次のユーザー発言と
 * 誤ってペアにされてしまう)。
 */
function chunkIntoTurns(messages: ChatMessageType[]): Turn[] {
  const turns: Turn[] = []
  let i = 0
  while (i < messages.length) {
    const current = messages[i]
    if (current.role === "user") {
      const next = messages[i + 1]
      const assistant = next?.role === "assistant" ? next : undefined
      turns.push({ user: current, assistant, index: turns.length + 1 })
      i += assistant ? 2 : 1
    } else {
      // 対になるユーザー発言を持たないアシスタント単独のターン(プロアクティブな一言)
      turns.push({ user: undefined, assistant: current, index: turns.length + 1 })
      i += 1
    }
  }
  return turns
}

// この距離(px)より下側にいれば「まだ最下部付近にいる」とみなし、新着分を
// 自動追従する。これより上へ自分でスワイプ/スクロールしたら、その位置を
// 尊重して自動では下まで連れ戻さない(触らなければ引き続き最下部まで追従する)。
const NEAR_BOTTOM_THRESHOLD_PX = 120

/**
 * 生成中でも次のメッセージを送れるようにしたため、「配列の最後の要素だけが
 * ストリーミング中」とは限らない。各メッセージ自身の_localIdが振られているか
 * (=まだ完了していないアシスタント発言か)で、メッセージごとにストリーミング中かを判定する。
 * 完了した発言からは呼び出し側(app/page.tsx)が_localIdを外さないため、
 * 代わりにcontentの有無だけでなく「_localIdが付いている」ことそのものを
 * ストリーミング中の目印として扱う。
 */
export function ChatMessages({ messages }: ChatMessagesProps) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const viewportRef = useRef<HTMLDivElement>(null)
  // ユーザーが自分で上へスワイプ/スクロールした場合、streaming中の新着トークンで
  // 勝手に最下部へ引き戻さないようにするためのフラグ(scrollイベントのたびに
  // 更新するだけなのでrenderを起こさないrefで持つ)
  const isNearBottomRef = useRef(true)

  useEffect(() => {
    const viewport = viewportRef.current
    if (!viewport) return

    const handleScroll = () => {
      const distanceFromBottom =
        viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight
      isNearBottomRef.current = distanceFromBottom <= NEAR_BOTTOM_THRESHOLD_PX
    }

    viewport.addEventListener("scroll", handleScroll, { passive: true })
    return () => viewport.removeEventListener("scroll", handleScroll)
  }, [])

  useEffect(() => {
    if (!isNearBottomRef.current) return
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  const turns = chunkIntoTurns(messages)

  return (
    <ScrollArea className="flex-1 w-full" viewportRef={viewportRef}>
      <div className="mx-auto flex w-full max-w-3xl flex-col px-4 py-8 sm:px-6">
        {turns.map((turn) => (
          <section key={turn.index} className="mt-16 flex flex-col gap-3 first:mt-0">
            {turn.user && <ChatMessage message={turn.user} isStreamingNow={false} />}
            {turn.assistant && (
              <ChatMessage
                message={turn.assistant}
                isStreamingNow={turn.assistant._localId !== undefined}
                turnIndex={turn.index}
              />
            )}
          </section>
        ))}
        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  )
}
