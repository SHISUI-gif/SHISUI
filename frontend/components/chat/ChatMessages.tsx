import { useEffect, useRef } from "react"
import { ScrollArea } from "@/components/ui/scroll-area"
import type { ChatMessage as ChatMessageType } from "@/lib/types"
import { ChatMessage } from "./ChatMessage"

interface ChatMessagesProps {
  messages: ChatMessageType[]
  toolStatus?: string
  isStreaming?: boolean
}

export function ChatMessages({ messages, toolStatus, isStreaming }: ChatMessagesProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, toolStatus])

  return (
    <ScrollArea className="flex-1 w-full">
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-8 sm:px-6">
        {messages.map((message, index) => (
          <ChatMessage
            key={index}
            message={message}
            isStreamingNow={Boolean(isStreaming) && index === messages.length - 1}
          />
        ))}
        {toolStatus && (
          <p className="font-mono text-[10px] tracking-wider text-[#c8ff00]/60 uppercase">{toolStatus}</p>
        )}
        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  )
}
