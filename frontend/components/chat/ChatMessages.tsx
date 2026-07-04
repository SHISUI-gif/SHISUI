import { useEffect, useRef } from "react"
import { ScrollArea } from "@/components/ui/scroll-area"
import type { ChatMessage as ChatMessageType } from "@/lib/types"
import { ChatMessage } from "./ChatMessage"

interface ChatMessagesProps {
  messages: ChatMessageType[]
}

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

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  return (
    <ScrollArea className="flex-1 w-full">
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-8 sm:px-6">
        {messages.map((message, index) => (
          <ChatMessage
            key={index}
            message={message}
            isStreamingNow={message._localId !== undefined}
          />
        ))}
        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  )
}
