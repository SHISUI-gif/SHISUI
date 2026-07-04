"use client"

import { useState } from "react"
import { AnimatePresence, motion } from "framer-motion"
import { DURATION, EASE } from "@/lib/motion"
import type { EvolutionProposal } from "@/lib/types"

interface EvolutionProposalsProps {
  isOpen: boolean
  onClose: () => void
  proposals: EvolutionProposal[]
  onApply: (id: string) => Promise<void>
  onReject: (id: string) => Promise<void>
}

function DiffView({ diff }: { diff: string }) {
  return (
    <pre className="mt-2 max-h-64 overflow-auto rounded border border-white/10 bg-white/5 p-2 font-mono text-[10px] leading-relaxed">
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
        className="mt-2 font-mono text-[10px] uppercase tracking-widest text-white/40 hover:text-[#c8ff00]"
      >
        {diffOpen ? "差分を隠す" : "差分を見る"}
      </button>
      {diffOpen && <DiffView diff={proposal.diff} />}

      <div className="mt-3 flex gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={handleApplyClick}
          className="flex-1 border border-[#c8ff00]/40 py-2 font-mono text-[10px] uppercase tracking-widest text-[#c8ff00] hover:bg-[#c8ff00]/10 disabled:opacity-40"
        >
          {confirmingApply ? "本当に適用する?" : "承認"}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={handleReject}
          className="flex-1 border border-white/20 py-2 font-mono text-[10px] uppercase tracking-widest text-white/50 hover:text-white disabled:opacity-40"
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
 */
export function EvolutionProposals({
  isOpen,
  onClose,
  proposals,
  onApply,
  onReject,
}: EvolutionProposalsProps) {
  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            key="evolution-backdrop"
            className="fixed inset-0 z-40 bg-black/60"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: DURATION.fast, ease: EASE }}
            onClick={onClose}
          />

          <motion.div
            key="evolution-drawer"
            className="fixed inset-y-0 right-0 z-50 flex w-72 flex-col border-l border-white/10 bg-black"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ duration: DURATION.base, ease: EASE }}
          >
            <div className="flex items-center justify-between border-b border-white/10 p-4">
              <p className="font-mono text-xs uppercase tracking-widest text-white/70">
                承認待ちの修正案
              </p>
              <button
                type="button"
                onClick={onClose}
                aria-label="閉じる"
                className="text-white/40 hover:text-[#c8ff00]"
              >
                ×
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-4">
              {proposals.length === 0 && (
                <p className="font-mono text-[10px] text-white/25">
                  承認待ちの修正案はありません
                </p>
              )}
              <div className="flex flex-col gap-4">
                {proposals.map((proposal) => (
                  <ProposalCard
                    key={proposal.id}
                    proposal={proposal}
                    onApply={onApply}
                    onReject={onReject}
                  />
                ))}
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
