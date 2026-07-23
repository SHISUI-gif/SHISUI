import type { ChatMessage, ChatStreamEvent } from "./types"

/**
 * セッションが無効(未ログイン・トークン失効)だったことを示すエラー。
 * 呼び出し側はこれを拾って「エラーが発生しちゃった」という生の技術メッセージを
 * 見せるのではなく、ログイン画面へ戻す(何が起きたか分からない詰み状態を防ぐ)。
 */
export class AuthError extends Error {}

/**
 * 志粋のFastAPIバックエンド(/api/chat)へ問い合わせ、NDJSON形式のイベントを
 * 逐次yieldする非同期ジェネレータ。1行が1つのChatStreamEvent(JSON)に対応する。
 *
 * 常に同一オリジンの相対パスで呼び出す。実際の転送先(127.0.0.1:8000)は
 * next.config.tsのrewritesがサーバー側で解決するため、ブラウザがLAN経由・
 * 外部トンネル経由のどちらでアクセスしていても、フロントエンド側は
 * ホスト名を一切意識しなくてよい。
 *
 * conversationIdがnull(新しい会話)の場合、サーバー側が新規作成して
 * 各イベントのconversation_idとして返してくる。呼び出し側はそれを拾って
 * 以降のメッセージに使う。
 *
 * signalを渡すと、誤送信時などに呼び出し側でfetch自体を中断できる
 * (中断時はDOMException "AbortError"がそのままthrowされるので、
 * 呼び出し側でエラー扱いせず区別すること)。
 */
export async function* streamChat(
  message: string,
  history: ChatMessage[],
  token: string,
  conversationId: number | null,
  signal?: AbortSignal,
): AsyncGenerator<ChatStreamEvent> {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      message,
      history: history.map((m) => ({ role: m.role, content: m.content })),
      conversation_id: conversationId,
    }),
    signal,
  })

  if (response.status === 401) {
    throw new AuthError("セッションが切れました。もう一度ログインしてください。")
  }
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

/**
 * チャット画面を開いたまま数分間発言が無かったとき、志粋から自然に話しかける
 * 一言を取得する(呼び出し元は一定間隔でこれをポーリングする想定)。
 * 生成された発話はサーバー側で会話履歴にも保存されるため、リロードしても残る。
 */
/**
 * 志粋がその場で何も生成できなかった場合(ローカルLLMがまれに空応答を返す
 * 既知の癖)はnullを返す。呼び出し側はnullの場合、吹き出しを追加しないこと。
 */
export async function fetchProactiveCheckin(token: string, conversationId: number): Promise<string | null> {
  const response = await fetch(`/api/conversations/${conversationId}/proactive-checkin`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  })

  if (response.status === 401) {
    throw new AuthError("セッションが切れました。もう一度ログインしてください。")
  }
  if (!response.ok) {
    throw new Error(`志粋APIへの接続に失敗しました (HTTP ${response.status})`)
  }

  const body = await response.json()
  return (body.content as string | null) ?? null
}
