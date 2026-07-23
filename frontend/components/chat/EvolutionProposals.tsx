"use client"

import { useEffect, useRef, useState } from "react"
import { AnimatePresence, motion } from "framer-motion"
import { GlowBlob } from "@/components/GlowBlob"
import { DURATION, EASE } from "@/lib/motion"
import type { EvolutionProposal } from "@/lib/types"

/**
 * 一覧の各カードをモーダルのスライドが落ち着いた後に少し遅れてカスケード表示
 * させるためのvariants(ActivityLog.tsxと同じ考え方)。
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

interface EvolutionProposalsProps {
  isOpen: boolean
  onClose: () => void
  proposals: EvolutionProposal[]
  onApply: (id: string) => Promise<void>
  onReject: (id: string) => Promise<void>
}

/**
 * マウス位置に追従する、ぼかしたアクセントカラーのグロー(ActivityLog.tsxと同じ演出)。
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

function DiffView({ diff }: { diff: string }) {
  return (
    <pre className="mt-2 max-h-64 overflow-auto rounded-xl border border-white/10 bg-white/5 p-2 font-mono text-[10px] leading-relaxed">
      {diff.split("\n").map((line, index) => {
        let color = "text-white/50"
        if (line.startsWith("+") && !line.startsWith("+++")) color = "text-green-400"
        else if (line.startsWith("-") && !line.startsWith("---")) color = "text-red-400"
        return (
          <div key={index} className={color}>
            {line}
          </div>
        )
      })}
    </pre>
  )
}

function ProposalCard({
  proposal,
  onApply,
  onReject,
}: {
  proposal: EvolutionProposal
  onApply: (id: string) => Promise<void>
  onReject: (id: string) => Promise<void>
}) {
  const [diffOpen, setDiffOpen] = useState(false)
  const [confirmingApply, setConfirmingApply] = useState(false)
  const [busy, setBusy] = useState(false)

  const handleApplyClick = async () => {
    if (!confirmingApply) {
      setConfirmingApply(true)
      return
    }
    setBusy(true)
    await onApply(proposal.id)
    setBusy(false)
  }

  const handleReject = async () => {
    setBusy(true)
    await onReject(proposal.id)
    setBusy(false)
  }

  return (
    <div className="border-b border-white/5 pb-4">
      <p className="font-mono text-[10px] text-white/40">{proposal.file_path}</p>
      <p className="mt-1 text-sm text-white/80">{proposal.explanation}</p>

      <button
        type="button"
        onClick={() => setDiffOpen((v) => !v)}
        className="mt-2 font-mono text-[10px] uppercase tracking-widest text-white/40 hover:text-[#b8935a]"
      >
        {diffOpen ? "差分を隠す" : "差分を見る"}
      </button>
      {diffOpen && <DiffView diff={proposal.diff} />}

      <div className="mt-3 flex gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={handleApplyClick}
          className="flex-1 rounded-full border border-[#b8935a]/40 py-2 font-mono text-[10px] uppercase tracking-widest text-[#b8935a] hover:bg-[#b8935a]/10 disabled:opacity-40"
        >
          {confirmingApply ? "本当に適用する?" : "承認"}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={handleReject}
          className="flex-1 rounded-full border border-white/20 py-2 font-mono text-[10px] uppercase tracking-widest text-white/50 hover:text-white disabled:opacity-40"
        >
          却下
        </button>
      </div>
    </div>
  )
}

/**
 * 自己修復提案(src/core/evolution.py)の承認待ち一覧を、オーナーがスマホからでも
 * 確認・承認/却下できるようにするパネル。承認はgit commitする不可逆操作なので、
 * ボタンを1回押すと「本当に適用する?」に切り替わる簡易確認を挟む
 * (native confirm()は使わず、既存の中断UXと統一する)。
 *
 * ActivityLog.tsxと同じカード構成のモーダルに統一(左に概要カード+件数の
 * 円形フレーム、右に対象ファイルの内訳、下に全提案の実際の承認/却下UI)。
 */
export function EvolutionProposals({
  isOpen,
  onClose,
  proposals,
  onApply,
  onReject,
}: EvolutionProposalsProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const glow = useCursorGlow(containerRef)

  const uniqueFiles = new Set(proposals.map((p) => p.file_path)).size

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            key="evolution-backdrop"
            className="fixed inset-0 z-40 bg-black/80"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: DURATION.fast, ease: EASE }}
            onClick={onClose}
          />

          <motion.div
            key="evolution-modal"
            ref={containerRef}
            className="fixed inset-4 z-50 overflow-hidden rounded-3xl border border-white/10 bg-[#0a0a0a] shadow-[inset_0_1px_0_rgba(255,255,255,0.08)] sm:inset-10 lg:inset-16"
            initial={{ opacity: 0, scale: 0.97 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.97 }}
            transition={{ duration: DURATION.base, ease: EASE }}
          >
            {/* 立体感を出すための、ぼかしたアクセントカラーの光の層+粒状テクスチャ(背景) */}
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
              <p className="font-mono text-xs uppercase tracking-widest text-white/70">
                承認待ちの修正案
              </p>

              <div className="mt-8 grid gap-4 lg:grid-cols-[2fr_1fr]">
                {/* 左: 件数を大きく見せる概要カード */}
                <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-6 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] backdrop-blur-xl sm:p-8">
                  <p className="font-mono text-[10px] uppercase tracking-wider text-[#b8935a]/70">
                    自己修復プロトコル
                  </p>
                  <p className="mt-2 text-lg text-white/80">
                    志粋が検出したエラーへの修正案です。承認するとgit commitとして実際のコードに反映されます。
                  </p>

                  <div className="flex items-center justify-center py-8">
                    <div className="relative flex h-40 w-40 items-center justify-center rounded-full border border-dashed border-white/20 sm:h-48 sm:w-48">
                      <GlowBlob className="inset-4 bg-[#b8935a]/[0.14]" />
                      <div className="relative text-center">
                        <p className="font-[family-name:var(--font-syne)] text-4xl font-bold text-white">
                          {proposals.length}
                        </p>
                        <p className="mt-1 font-mono text-[9px] uppercase tracking-widest text-white/40">
                          承認待ち
                        </p>
                      </div>
                    </div>
                  </div>
                </div>

                {/* 右: 対象ファイルの内訳 */}
                <div className="flex flex-col gap-4">
                  <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-6 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] backdrop-blur-xl">
                    <p className="font-[family-name:var(--font-syne)] text-lg font-bold text-white">
                      対象範囲
                    </p>
                    <div className="mt-4 space-y-3">
                      <div className="flex items-center justify-between font-mono text-xs">
                        <span className="text-white/40">対象ファイル数</span>
                        <span className="text-white/70">{uniqueFiles}件</span>
                      </div>
                      <div className="flex items-center justify-between font-mono text-xs">
                        <span className="text-white/40">承認方式</span>
                        <span className="text-white/70">要人間確認</span>
                      </div>
                    </div>
                  </div>

                  <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-6 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] backdrop-blur-xl">
                    <p className="font-[family-name:var(--font-syne)] text-lg font-bold text-white">注意</p>
                    <p className="mt-3 font-mono text-[10px] leading-relaxed text-white/50">
                      承認は不可逆操作です。差分を確認してから承認してください。
                    </p>
                  </div>
                </div>
              </div>

              {/* 下: 全提案の実際の承認/却下UI */}
              <div className="mt-10 rounded-2xl border border-white/10 bg-white/[0.02] p-6 backdrop-blur-xl">
                <p className="font-mono text-[10px] uppercase tracking-widest text-white/40">
                  すべての提案
                </p>
                {proposals.length === 0 && (
                  <p className="mt-4 font-mono text-[10px] text-white/25">
                    承認待ちの修正案はありません
                  </p>
                )}
                <motion.div
                  className="mt-4 flex flex-col gap-4"
                  variants={listContainer}
                  initial="hidden"
                  animate="visible"
                >
                  {proposals.map((proposal) => (
                    <motion.div key={proposal.id} variants={listItem}>
                      <ProposalCard proposal={proposal} onApply={onApply} onReject={onReject} />
                    </motion.div>
                  ))}
                </motion.div>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
