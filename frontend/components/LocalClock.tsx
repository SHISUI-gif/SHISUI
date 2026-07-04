"use client"

import { useEffect, useState } from "react"

function formatTime(date: Date): string {
  const hours = date.getHours()
  const minutes = date.getMinutes().toString().padStart(2, "0")
  const meridiem = hours < 12 ? "AM" : "PM"
  const hour12 = hours % 12 || 12
  return `${hour12}:${minutes}${meridiem}`
}

function formatDate(date: Date): string {
  const months = [
    "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
    "JUL", "AUG", "SEP", "OCT", "NOV", "DEC",
  ]
  return `${date.getDate()} ${months[date.getMonth()]}`
}

/**
 * ホーム画面にさりげなく置く、自律型AIが「今」を把握していることを示すための
 * ローカル時刻表示。角丸ゼロ・モノスペース・ライム/白のみというサイト全体の
 * デザイン原則を踏襲する。初回レンダー(サーバー側)ではまだ時刻が無いため
 * 何も表示しない(hydrationミスマッチを避ける)。
 */
export function LocalClock() {
  const [now, setNow] = useState<Date | null>(null)

  useEffect(() => {
    setNow(new Date())
    const interval = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(interval)
  }, [])

  if (!now) return null

  return (
    <div className="flex items-center gap-2 border border-white/10 px-3 py-1.5 font-mono text-[10px] tracking-[0.2em] text-white/40 uppercase">
      <span>{formatDate(now)}</span>
      <span className="text-white/15">/</span>
      <span className="tabular-nums text-[#c8ff00]/70">{formatTime(now)}</span>
    </div>
  )
}
