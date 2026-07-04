import ReactMarkdown from "react-markdown"
import rehypeRaw from "rehype-raw"
import remarkGfm from "remark-gfm"
import { cn } from "@/lib/utils"

interface MarkdownContentProps {
  content: string
  className?: string
}

// CommonMarkの強調記法は「**」の前後が句読点か通常文字かで開始/終了として
// 認識されるかどうかが変わる(flanking rule)。日本語の「」の直後に
// スペース無しで文字が続く「**「心の奥に響く」**もの」のようなケースは、
// 閉じ「**」の前が句読点(」)・後ろが通常文字(も)になり「閉じ」の条件を
// 満たさず、太字として解釈されずアスタリスクがそのまま表示されてしまう。
// remarkのASTレベルの強調解析はこの規則を変更できないため、太字だけは
// 先にHTMLの<strong>へ変換してから渡し、rehype-rawでHTMLとして解釈させる。
//
// ただしコードフェンス(```)・インラインコード(`)の中は絶対に触らない
// (`**kwargs`や`2**10`のようなコード中のアスタリスクを太字化してしまうため)。
function boldToStrong(text: string): string {
  return text.replace(/\*\*([^*]+?)\*\*/g, "<strong>$1</strong>")
}

function convertBoldToRawHtml(content: string): string {
  const codeSegmentPattern = /```[\s\S]*?```|`[^`]*`/g
  let result = ""
  let lastIndex = 0
  let match: RegExpExecArray | null
  while ((match = codeSegmentPattern.exec(content)) !== null) {
    result += boldToStrong(content.slice(lastIndex, match.index))
    result += match[0]
    lastIndex = match.index + match[0].length
  }
  result += boldToStrong(content.slice(lastIndex))
  return result
}

/**
 * 志粋の応答をMarkdownとして解釈して表示する。
 * それまでは content をそのまま<p>に流し込んでいたため、**太字**のような
 * Markdown記法がアスタリスク付きの生テキストとして表示されてしまっていた。
 */
export function MarkdownContent({ content, className }: MarkdownContentProps) {
  return (
    <div className={cn("text-sm leading-relaxed", className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRaw]}
        components={{
          p: ({ children }) => <p className="mb-2 last:mb-0 whitespace-pre-wrap">{children}</p>,
          strong: ({ children }) => <strong className="font-semibold text-white">{children}</strong>,
          em: ({ children }) => <em className="italic">{children}</em>,
          ul: ({ children }) => <ul className="mb-2 list-disc space-y-1 pl-5 last:mb-0">{children}</ul>,
          ol: ({ children }) => <ol className="mb-2 list-decimal space-y-1 pl-5 last:mb-0">{children}</ol>,
          li: ({ children }) => <li>{children}</li>,
          code: ({ children }) => (
            <code className="rounded bg-white/10 px-1 py-0.5 font-mono text-[0.85em]">{children}</code>
          ),
          pre: ({ children }) => (
            <pre className="mb-2 overflow-x-auto rounded-md bg-white/10 p-3 font-mono text-[0.85em] last:mb-0">
              {children}
            </pre>
          ),
          a: ({ children, href }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[#c8ff00] underline underline-offset-2 hover:text-[#c8ff00]/70"
            >
              {children}
            </a>
          ),
        }}
      >
        {convertBoldToRawHtml(content)}
      </ReactMarkdown>
    </div>
  )
}
