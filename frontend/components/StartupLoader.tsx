"use client"

import { useEffect, useState } from "react"
import { AnimatePresence, motion } from "framer-motion"
import { EASE } from "@/lib/motion"

interface StartupLoaderProps {
  onDone?: () => void
}

/**
 * 起動時に一瞬だけ表示するプログレスカウンター+ワイプ演出。
 * ツールとしての使い勝手を優先し、意図的な待機時間は最小限(1秒未満)に留める
 * — マーケティングサイトのような2秒以上の「わざと待たせる」演出は採用しない。
 */
export function StartupLoader({ onDone }: StartupLoaderProps) {
  const [progress, setProgress] = useState(0)
  const [done, setDone] = useState(false)

  useEffect(() => {
    const interval = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 100) {
          clearInterval(interval)
          return 100
        }
        return Math.min(100, prev + Math.random() * 30)
      })
    }, 60)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    if (progress >= 100) {
      const timeout = setTimeout(() => {
        setDone(true)
        onDone?.()
      }, 150)
      return () => clearTimeout(timeout)
    }
  }, [progress, onDone])

  return (
    <AnimatePresence>
      {!done && (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black"
          exit={{ y: "-100%" }}
          transition={{ duration: 0.6, ease: EASE }}
        >
          <span className="font-mono text-sm tracking-[0.3em] text-[#c8ff00]/70">
            {Math.floor(progress)}%
          </span>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
