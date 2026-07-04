import type { ChatMessage, ChatStreamEvent } from "./types"

/**
 * 志粋のFastAPIバックエンド(/api/chat)へ問い合わせ、NDJSON形式のイベントを
 * 逐次yieldする非同期ジェネレータ。1行が1つのChatStreamEvent(JSON)に対応する。
 *
 * 常に同一オリジンの相対パスで呼び出す。実際の転送先(127.0.0.1:8000)は
 * next.config.tsのrewritesがサーバー側で解決するため、ブラウザがLAN経由・
 * 外部トンネル経由のどちらでアクセスしていても、フロントエンド側は
 * ホスト名を一切意識しなくてよい。
 */
export async function* streamChat(
  message: string,
  history: ChatMessage[],
): AsyncGenerator<ChatStreamEvent> {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      history: history.map((m) => ({ role: m.role, content: m.content })),
    }),
  })

  if (!response.ok || !response.body) {
    throw new Error(`志粋APIへの接続に失敗しました (HTTP ${response.status})`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split("\n")
    buffer = lines.pop() ?? ""

    for (const line of lines) {
      if (!line.trim()) continue
      try {
        yield JSON.parse(line) as ChatStreamEvent
      } catch {
        // 不正な行はスキップする(接続の途中経過などでJSONが分断された場合の保険)
      }
    }
  }

  if (buffer.trim()) {
    try {
      yield JSON.parse(buffer) as ChatStreamEvent
    } catch {
      // 最終行が不完全な場合は無視する
    }
  }
}
