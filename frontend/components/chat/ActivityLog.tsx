"use client"

import { useEffect, useRef, useState } from "react"
import { AnimatePresence, motion } from "framer-motion"
import { GlowBlob } from "@/components/GlowBlob"
import { DURATION, EASE } from "@/lib/motion"
import type { ActivityEntry } from "@/lib/types"

/**
 * 一覧の各エントリをドロワー本体のスライドが落ち着いた後に少し遅れてカスケード表示
 * させるためのvariants。app/page.tsxのstaggerContainer/fadeUpと同じ考え方
 * (EASEを共有・小さめのstaggerChildren)をリスト項目向けに調整したもの。
 */
const listContainer = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.04, delayChildren: 0.2 },
  },
}

const listItem = {
  hidden: { opacity: 0, y: 10 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: DURATION.fast, ease: EASE },
  },
}

interface ActivityLogProps {
  isOpen: boolean
  onClose: () => void
  activities: ActivityEntry[]
}

const KIND_LABEL: Record<ActivityEntry["kind"], string> = {
  sleep: "💤 睡眠モード",
  study: "📚 夜間修行",
  debate: "💬 自律討論",
  self_repair: "🔧 自己修復",
  external_dialogue: "🌐 夜間対話",
}

/** debate/external_dialogueのdetailsから、話者ごとの発言リストを取り出す。
 * それまでconclusion_summary/insight(要約)しか無く、実際のやり取りが
 * 一切見えなかった(2026-07-29、那由多さんの要望で追加)。両方の形を
 * 共通の { topic, entries: {who, content}[] }[] に正規化する。 */
function extractTranscripts(
  activity: ActivityEntry
): { topic: string; entries: { who: string; content: string }[] }[] {
  const details = activity.details as Record<string, unknown>

  if (activity.kind === "debate" && Array.isArray(details.transcripts)) {
    return (details.transcripts as { topic: string; transcript: { speaker: string; content: string }[] }[]).map(
      (t) => ({
        topic: t.topic,
        entries: (t.transcript ?? []).map((e) => ({ who: e.speaker, content: e.content })),
      })
    )
  }

  if (activity.kind === "external_dialogue" && Array.isArray(details.dialogues)) {
    return (details.dialogues as { topic: string; dialogue: { role: string; content: string }[] }[]).map(
      (t) => ({
        topic: t.topic,
        entries: (t.dialogue ?? []).map((e) => ({ who: e.role, content: e.content })),
      })
    )
  }

  return []
}

/**
 * マウス位置に追従する、ぼかしたアクセントカラーのグロー。ユーザーが共有したUI参考の
 * 「カーソル追従の光」演出を、志粋の単色アクセントカラーの範囲内で再現する。
 * コンテナ自身のmousemoveだけを見るため、他のドロワー/画面には影響しない。
 */
function useCursorGlow(containerRef: React.RefObject<HTMLDivElement | null>) {
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return

    const handleMove = (event: MouseEvent) => {
      const rect = el.getBoundingClientRect()
      setPos({ x: event.clientX - rect.left, y: event.clientY - rect.top })
    }

    el.addEventListener("mousemove", handleMove)
    return () => el.removeEventListener("mousemove", handleMove)
  }, [containerRef])

  return pos
}

/**
 * 睡眠モード・夜間修行・自律討論など、志粋が那由多さんの見ていないところで
 * 自律的に行っている活動を見せるパネル。特定の友達の会話ではなく志粋自身の
 * 活動なので、誰がログインしても同じ内容が見える(src/api/main.py:get_activity参照)。
 *
 * ユーザーが共有したUI参考(カード構成のモーダル+カーソル追従の光+丸み・
 * ぼかしの立体感)に寄せて再構成: 左に最新の活動を大きく見せるカード、右に
 * 種類別の内訳・概要カード、下に全記録の時系列リスト。数値は実際の
 * activities配列から集計したものだけを使い、架空の統計は表示しない。
 * この参考UIへの忠実さを優先し、モーダル/カードは丸みを持たせている
 * (志粋の他画面が守る「角丸ゼロ」の例外として明示的に許可された箇所)。
 */
export function ActivityLog({ isOpen, onClose, activities }: ActivityLogProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const glow = useCursorGlow(containerRef)
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null)

  const latest = activities[0]
  const counts = activities.reduce<Record<string, number>>((acc, activity) => {
    acc[activity.kind] = (acc[activity.kind] ?? 0) + 1
    return acc
  }, {})

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            key="activity-backdrop"
            className="fixed inset-0 z-40 bg-black/80"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: DURATION.fast, ease: EASE }}
            onClick={onClose}
          />

          <motion.div
            key="activity-modal"
            ref={containerRef}
            className="fixed inset-4 z-50 overflow-hidden rounded-3xl border border-white/10 bg-[#0a0a0a] shadow-[inset_0_1px_0_rgba(255,255,255,0.08)] sm:inset-10 lg:inset-16"
            initial={{ opacity: 0, scale: 0.97 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.97 }}
            transition={{ duration: DURATION.base, ease: EASE }}
          >
            {/* 立体感を出すための、ぼかしたアクセントカラーの光の層+粒状テクスチャ(背景)。
                固定の2つの発光源+カーソル追従の1つを重ねて、奥行きのある空気感を作る */}
            <GlowBlob className="-right-1/4 -top-1/3 h-[70%] w-[70%] bg-[#b8935a]/[0.10]" />
            <GlowBlob className="-bottom-1/3 -left-1/4 h-[60%] w-[60%] bg-[#b8935a]/[0.07]" />
            <div
              aria-hidden="true"
              className="pointer-events-none absolute inset-0 opacity-20 blur-3xl transition-[background] duration-150"
              style={{
                background: glow
                  ? `radial-gradient(420px circle at ${glow.x}px ${glow.y}px, #b8935a, transparent 70%)`
                  : "none",
              }}
            />

            <button
              type="button"
              onClick={onClose}
              aria-label="閉じる"
              className="absolute right-4 top-4 z-10 flex min-h-11 min-w-11 items-center justify-center rounded-full text-white/40 hover:bg-white/5 hover:text-[#b8935a]"
            >
              ×
            </button>

            <div className="relative flex h-full flex-col overflow-y-auto p-6 sm:p-10">
              <p className="font-mono text-xs uppercase tracking-widest text-white/70">活動ログ</p>

              <div className="mt-8 grid gap-4 lg:grid-cols-[2fr_1fr]">
                {/* 左: 最新の活動を大きく見せるカード */}
                <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-6 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] backdrop-blur-xl sm:p-8">
                  <p className="font-mono text-[10px] uppercase tracking-wider text-[#b8935a]/70">
                    {latest ? KIND_LABEL[latest.kind] : "まだ活動記録がありません"}
                  </p>
                  <p className="mt-2 text-lg text-white/80">
                    {latest?.summary ?? "1日1回の睡眠モードで記録されます"}
                  </p>

                  <div className="mt-8 flex items-center justify-center py-8">
                    <div className="relative flex h-40 w-40 items-center justify-center rounded-full border border-dashed border-white/20 sm:h-48 sm:w-48">
                      <GlowBlob className="inset-4 bg-[#b8935a]/[0.14]" />
                      <div className="relative text-center">
                        <p className="font-[family-name:var(--font-syne)] text-4xl font-bold text-white">
                          {activities.length}
                        </p>
                        <p className="mt-1 font-mono text-[9px] uppercase tracking-widest text-white/40">
                          記録件数
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="mt-8 space-y-3 border-t border-white/10 pt-4">
                    <div className="flex items-center justify-between font-mono text-xs">
                      <span className="text-white/40">最新の記録</span>
                      <span className="text-white/70">{latest?.timestamp ?? "—"}</span>
                    </div>
                    <div className="flex items-center justify-between font-mono text-xs">
                      <span className="text-white/40">対象</span>
                      <span className="text-white/70">睡眠・学習・討論</span>
                    </div>
                  </div>
                </div>

                {/* 右: 種類別の内訳カード */}
                <div className="flex flex-col gap-4">
                  <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-6 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] backdrop-blur-xl">
                    <p className="font-[family-name:var(--font-syne)] text-lg font-bold text-white">
                      種類別の内訳
                    </p>
                    <div className="mt-4 space-y-3">
                      <div className="flex items-center justify-between font-mono text-xs">
                        <span className="text-white/40">睡眠モード</span>
                        <span className="text-white/70">{counts.sleep ?? 0}件</span>
                      </div>
                      <div className="flex items-center justify-between font-mono text-xs">
                        <span className="text-white/40">夜間修行</span>
                        <span className="text-white/70">{counts.study ?? 0}件</span>
                      </div>
                      <div className="flex items-center justify-between font-mono text-xs">
                        <span className="text-white/40">自律討論</span>
                        <span className="text-white/70">{counts.debate ?? 0}件</span>
                      </div>
                      <div className="flex items-center justify-between font-mono text-xs">
                        <span className="text-white/40">自己修復</span>
                        <span className="text-white/70">{counts.self_repair ?? 0}件</span>
                      </div>
                      <div className="flex items-center justify-between font-mono text-xs">
                        <span className="text-white/40">夜間対話</span>
                        <span className="text-white/70">{counts.external_dialogue ?? 0}件</span>
                      </div>
                    </div>
                  </div>

                  <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-6 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] backdrop-blur-xl">
                    <p className="font-[family-name:var(--font-syne)] text-lg font-bold text-white">概要</p>
                    <div className="mt-4 space-y-3">
                      <div className="flex items-center justify-between font-mono text-xs">
                        <span className="text-white/40">記録期間</span>
                        <span className="text-white/70">
                          {activities.length > 0
                            ? `${activities[activities.length - 1].timestamp.slice(0, 10)} 〜`
                            : "—"}
                        </span>
                      </div>
                      <div className="flex items-center justify-between font-mono text-xs">
                        <span className="text-white/40">頻度</span>
                        <span className="text-white/70">1日1回(夜間)</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* 下: 全記録の時系列リスト */}
              <div className="mt-10 rounded-2xl border border-white/10 bg-white/[0.02] p-6 backdrop-blur-xl">
                <p className="font-mono text-[10px] uppercase tracking-widest text-white/40">すべての記録</p>
                {activities.length === 0 && (
                  <p className="mt-4 font-mono text-[10px] text-white/25">
                    まだ活動記録がありません(1日1回の睡眠モードで記録されます)
                  </p>
                )}
                <motion.div
                  className="mt-4 flex flex-col gap-4"
                  variants={listContainer}
                  initial="hidden"
                  animate="visible"
                >
                  {activities.map((activity, index) => {
                    const transcripts = extractTranscripts(activity)
                    const isExpanded = expandedIndex === index

                    return (
                      <motion.div
                        key={`${activity.timestamp}-${index}`}
                        variants={listItem}
                        className="border-b border-white/5 pb-3"
                      >
                        <p className="font-mono text-[10px] uppercase tracking-wider text-[#b8935a]/70">
                          {KIND_LABEL[activity.kind]}
                        </p>
                        <p className="mt-1 text-sm text-white/70">{activity.summary}</p>
                        <p className="mt-1 font-mono text-[10px] text-white/25">{activity.timestamp}</p>

                        {transcripts.length > 0 && (
                          <>
                            <button
                              type="button"
                              onClick={() => setExpandedIndex(isExpanded ? null : index)}
                              className="mt-2 font-mono text-[10px] text-[#b8935a]/70 hover:text-[#b8935a]"
                            >
                              {isExpanded ? "▲ 全文を閉じる" : "▼ 全文を見る"}
                            </button>

                            {isExpanded && (
                              <div className="mt-3 space-y-4 rounded-xl border border-white/10 bg-white/[0.03] p-4">
                                {transcripts.map((t, tIndex) => (
                                  <div key={tIndex}>
                                    <p className="font-mono text-[10px] uppercase tracking-wider text-white/40">
                                      {t.topic}
                                    </p>
                                    <div className="mt-2 space-y-2">
                                      {t.entries.map((entry, eIndex) => (
                                        <p key={eIndex} className="text-xs text-white/70">
                                          <span className="text-[#b8935a]/80">{entry.who}: </span>
                                          {entry.content}
                                        </p>
                                      ))}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            )}
                          </>
                        )}
                      </motion.div>
                    )
                  })}
                </motion.div>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
